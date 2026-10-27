# End-to-end studio

An office of skills that writes a competition proposal for any site in Weimar. One skill per person. The contract that holds them together is in [`OFFICE.md`](OFFICE.md).

A skill is a folder with a `SKILL.md`: a short Markdown file of instructions, with a `name` and a `description` at the top. Claude Code reads the descriptions of all skills in a project, and loads a skill when a task fits its description.

## Use a skill

Copy its folder from `skills/` into `.claude/skills/` in your project, then restart `claude`. Type `/` to check it's listed. Or ask your agent: "Copy the skill `general-plan` from github.com/Bauhaus-InfAU/end-to-end-studio into this project."

To run the whole office, copy all of `skills/` and ask for "a competition proposal for the site in `proposal/site.geojson`".

## Test without the others

`examples/weimar-block/proposal/` has a site and a finished massing. Copy that `proposal/` folder into your project, and your skill has everything it would get from the skills before it.

## Add or improve a skill

1. Fork this repo on GitHub (the Fork button, top right).
2. Ask your agent to clone your fork, make a branch named after your skill, and put your folder in `skills/<your-skill>/`.
3. Commit, push, and open a pull request against this repo. Fill in the template.
4. Change only your own folder. Then no two pull requests touch the same file, and nothing conflicts.

## Skills

| Skill | Status |
| --- | --- |
| `drawing-graphics` | example |
| `general-plan` | example |
| `competition-proposal` | the lead, runs the others |

Everything else in `OFFICE.md` is open.
