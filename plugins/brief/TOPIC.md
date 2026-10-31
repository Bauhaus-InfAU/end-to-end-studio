# Brief

Skills that read the brief and turn it into something the other skills can check against.

- Input: the brief and any document the user names, as the Markdown `pdf-to-md` (in `utilities`) writes next to each PDF, with page markers, so every number can be cited with its file and page.
- Output: `brief-reader` writes `checklist.md`: the numbers, the required drawings and their scales, the panel format, what the jury looks for. Other skills take their scales and formats from it.
- A new skill here: anything that reads the brief for one kind of requirement, such as the programme's areas or the submission rules.
