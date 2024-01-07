# dungeon-pipeline


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
   git clone -c core.sshCommand='ssh -i ~/.ssh/github'git@github.com:scottdmilner/dungeon-pipeline.git
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
