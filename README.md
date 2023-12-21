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
1. Check out your personal dev branch
   ```bash
   git checkout -B yourname-dev 
   # don't need -B if it already exists
   git push --set-upstream origin yourname-dev
   ```
