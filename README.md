# dungeon-pipeline

An OS-agnostic, portable, extensible 3D pipeline for the BYU Center for Animation's 2025 Capstone film, *Love & Dungeons*.

`dungeon-pipeline` is currently being used on EL8 and Windows 10 systems. It should also be functional on macOS systems, but that has not been tested.

## Repo structure
```
dungeon-pipeline/
├── Dungance Painter.lnk  # Linux and Windows launchers for DCCs. 
├── Dungaya.desktop       # These are at the root so they're easy for artists to locate
├── ...
├── LICENSE
├── pipeline
│   ├── env.py.md         # How to build set up env.py
│   ├── lib               # Python libraries and other resource files
│   ├── __main__.py
│   ├── pipe              # Python module for code that is imported and run from the DCC
│   ├── shared            # Utilities used by `pipe` and `software` modules
│   └── software          # Module called by `__main__.py` to initialize environments and launch DCCs
├── pyproject.toml
└── README.md
```

## Setting up a copy of `dungeon-pipeline`
1. Fork this repo and clone it to the production location.
1. Create an `pipeline/env.py` file following the specifications in `pipeline/env.py.md`. This will get things like ShotGrid auth set up, and provide OS-specific DCC executable paths.
1. Install needed python libraries into `pipeline/lib/python/any`. (This will soon by managed via Poetry (Issue #137), for now see the list in `.githooks/setup-venv.sh`).
1. Clone branches for development locally, copy over the env files and get to work!

## Setting up a dev environment in the labs
1. Generate a GitHub SSH key and upload it to your GitHub
   - ```bash
     ssh-keygen -t ed25519 -C "yourgithubemail@email.com"
     cat ~/.ssh/github.pub
     ```
   - When it asks for a path, type '/users/animation/yournetid/.ssh/github'
   - Only provide a passphrase if you want to type that every time you push or pull
   - Go to https://github.com/settings/keys and add the contents of `~/.ssh/github.pub` as a **New SSH key**
1. Make a local copy of the git repo
   ```bash
   cd ~/Documents
   git clone --recurse-submodules -c core.sshCommand='ssh -i ~/.ssh/github' git@github.com:scottdmilner/dungeon-pipeline.git
   cd dungeon-pipeline
   ```
1. Configure the git repo to use the new SSH key and our git hooks
   ```bash
   git config --add --local core.sshCommand 'ssh -i ~/.ssh/github'
   git config --local core.hooksPath .githooks/
   ```
1. Check out a dev branch for the feature you are working on (or create a general dev branch (`yourname-dev`))
   ```bash
   git checkout -B feature-name-yourname 
   # don't need -B if it already exists
   git push --set-upstream origin feature-name-yourname
   ```

## Code Style

For this project, we are using the Black style of Python formatting. There is a Git pre-commit hook that will automatically run the `ruff` formatter on your code whenever you make a commit. If it changes any of your formatting it will print a message that looks like this:

```
Formatting with ruff...
3 files reformatted, 12 files left unchanged
```

After that, you can amend your commit to include the changes that `ruff` made with

```bash
git add <changed files here>
git commit --amend
```

This should generally be avoided, but if you need to override the Black style for some reason, use the following comments to suppress `ruff`:

```python
...
# fmt: off
unformatted code here
# fmt: on
...
```
