"""Render a LaTeX manuscript as the text a quotation is checked against.

The quote backend reads a source through `citations.verify.extract`, which reads `.md`, `.txt`
and five other suffixes directly and sends everything else to `pdftotext`. `.tex` is on neither
list, so a manuscript declared as a `.tex` artifact comes back `unchecked` with
`pdftotext exited 1: Syntax Error: Couldn't read xref table`, and under any policy that grades
`unchecked` the whole self-audit fails without a single sentence having been read. This
produces the readable rendering the manifest pins beside the source.

Three rules decide what a sentence looks like once the markup is gone.

**Annotation and reference macros lose their argument.** `\\REVIEW{...}` is a note to the
author and `\\ref{tab:stages}` renders as a number, so keeping either welds text into a
sentence that no reader sees. In the abstract, `nineteen\\REVIEW{...} fixtures` is two words
with a paragraph of editorial notes between them; dropping the argument restores
`nineteen fixtures`.

**Every other macro keeps its argument.** `\\code{0.001}`, `\\textbf{145 are checkable}` and
`\\caption{...}` carry manuscript prose. Dropping the argument of an unrecognized command --
which is what a bibliography-field cleaner does -- deletes the number the assertion is about.

**Nothing is deleted without a separator taking its place.** A cell boundary `&` becomes
` | ` and a row break `\\\\` becomes a newline, so a quotation cannot silently span two cells;
this is the rule `citations.verify.fold` applies to control characters, one level up.

    python3 scripts/detex.py paper/manuscript.tex paper/manuscript.txt

Standard library only, and no import of `sys`: `repro`'s regeneration sandbox copies the
declared inputs into an empty directory and runs the command there, so anything this needs
beyond the interpreter is a defect in the declaration.
"""

from __future__ import annotations

import argparse
import pathlib
import re

#: A comment runs to the end of the line. `\%` is an escaped percent sign and is not one, which
#: is why the lookbehind is there: `8.3\%` would otherwise lose the rate it states.
COMMENT = re.compile(r"(?<!\\)%.*$", re.M)

CONTROL_WORD = re.compile(r"\\([a-zA-Z]+)\*?")

#: Macros whose argument is not prose: an editorial note, a cross-reference key, a citation
#: key, a file name, a length. Rendered output shows a number, a marker, or nothing at all.
DROP_ARGUMENT = frozenset(
    {
        "TODO",
        "FILLIN",
        "REVIEW",
        "label",
        "ref",
        "eqref",
        "pageref",
        "cite",
        "citep",
        "citet",
        "citealp",
        "citeauthor",
        "citeyear",
        "bibliography",
        "bibliographystyle",
        "input",
        "include",
        "usepackage",
        "documentclass",
        "hypersetup",
        "captionsetup",
        "newcommand",
        "renewcommand",
        "setlength",
        "vspace",
        "hspace",
        "includegraphics",
    }
)

#: Environments taking a mandatory column specification after their name. The specification is
#: layout and its braces nest -- `{@{}lp{3.6cm}}` -- so it is skipped as a balanced group.
COLUMN_SPEC = frozenset({"tabular", "tabularx", "array"})

#: Space introduced by unwrapping a macro, sitting where the source had none.
BEFORE_PUNCTUATION = re.compile(r" +([,.;:!?)\]])")
AFTER_OPENING = re.compile(r"([(\[]) +")


def balanced(text: str, start: int, opening: str = "{", closing: str = "}") -> tuple[str, int]:
    """The group beginning at `text[start]`, and the index just past its close.

    Balanced rather than regular, because a column specification, a `tcolorbox` title and a
    nested `\\textbf` all put braces inside braces, and a non-greedy `\\{[^}]*\\}` stops at the
    first inner close and leaves the rest of the group in the output as literal markup.
    """
    depth = 0
    for i in range(start, len(text)):
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
    return text[start + 1 :], len(text)


def _skip_optional(text: str, i: int) -> int:
    while i < len(text) and text[i] == "[":
        _, i = balanced(text, i, "[", "]")
    return i


def scan(tex: str) -> str:
    """Strip markup from one fragment, recursing into the arguments that are kept."""
    out: list[str] = []
    i = 0
    while i < len(tex):
        if tex[i] != "\\":
            out.append(" | " if tex[i] == "&" else tex[i])
            i += 1
            continue
        word = CONTROL_WORD.match(tex, i)
        if word is None:
            # `\%`, `\_`, `\&`, `\$`, `\#`, `\{`, `\}` are the character itself; `\\` ends a row.
            following = tex[i + 1 : i + 2]
            out.append("\n" if following == "\\" else following)
            i += 2 if following else 1
            continue
        name, i = word.group(1), word.end()
        if name in ("begin", "end"):
            environment = ""
            if i < len(tex) and tex[i] == "{":
                environment, i = balanced(tex, i)
            i = _skip_optional(tex, i)
            if name == "begin" and environment in COLUMN_SPEC and i < len(tex) and tex[i] == "{":
                _, i = balanced(tex, i)
            out.append("\n")
            continue
        i = _skip_optional(tex, i)
        if name in DROP_ARGUMENT:
            while i < len(tex) and tex[i] == "{":
                _, i = balanced(tex, i)
            out.append(" ")
            continue
        if i < len(tex) and tex[i] == "{":
            inner, i = balanced(tex, i)
            out.append(" " + scan(inner).strip() + " ")
        else:
            out.append(" ")
    return "".join(out)


def plain(tex: str) -> str:
    """The manuscript as a reader sees it: no preamble, no markup, one line per source line.

    Line structure is kept rather than reflowed. `fold` collapses whitespace before matching,
    so a quotation spanning a line break resolves either way, and keeping the lines makes the
    rendering diffable against the source it came from.
    """
    start = tex.find(r"\begin{document}")
    if start != -1:
        tex = tex[start + len(r"\begin{document}") :]
    text = scan(COMMENT.sub("", tex))
    text = text.replace("~", " ").replace("---", "\u2014").replace("--", "\u2013")
    text = re.sub(r"[{}]", "", text)
    text = AFTER_OPENING.sub(r"\1", BEFORE_PUNCTUATION.sub(r"\1", text))
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip()) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a LaTeX manuscript as plain text")
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("target", type=pathlib.Path)
    args = parser.parse_args(argv)
    args.target.write_text(plain(args.source.read_text()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
