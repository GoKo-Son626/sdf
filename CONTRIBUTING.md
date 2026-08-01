# Contributing

Thanks for helping improve SDF Translator. The project currently focuses on a reliable Arch Linux, Wayland, and niri experience while welcoming support for other distributions and desktop environments.

## Before you start

- Search existing issues before reporting a bug or proposing a feature.
- Report vulnerabilities according to [SECURITY.md](SECURITY.md); do not publish exploit details.
- Never commit API keys, proxy credentials, translation history, clipboard contents, or private logs.
- Keep dependencies minimal. Explain any new dependency and the alternatives considered in your pull request.

## Local development

```bash
git clone https://github.com/GoKo-Son626/sdf.git
cd sdf
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/check_repository.py
```

Install into the current Arch Linux user account for manual testing:

```bash
./install.sh --yes
```

## Submission guidelines

- Keep each commit focused and use a concise English commit message.
- Add a regression test when fixing a bug.
- Update the README when changing commands, configuration, installation, or user-facing behavior.
- Run the full test suite and privacy check before submitting; confirm that `git status` contains no personal files.
- Include the test platform in the pull request. Desktop integration changes should identify the Wayland compositor and editor or document viewer used.
