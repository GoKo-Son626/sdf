# Arch Linux and AUR packaging

The included `PKGBUILD` follows the Arch VCS package format and installs the latest Git revision as `sdf-translator-git`. The upstream source is <https://github.com/GoKo-Son626/sdf>.

The GitHub repository and the AUR package repository are separate Git repositories. Do not push the entire project history to AUR.

## One-time AUR setup

1. Register at <https://aur.archlinux.org/register>.
2. Add an SSH public key to the AUR account. A dedicated key is recommended.
3. Confirm that the intended package base is available.
4. Clone its AUR repository. An empty-repository warning is expected for a new package:

   ```bash
   git -c init.defaultBranch=master clone \
     ssh://aur@aur.archlinux.org/sdf-translator-git.git
   ```

5. Replace the maintainer comment in `PKGBUILD` with the real maintainer name and email.

## Validate before publishing

From this directory, build and inspect the package:

```bash
makepkg -Ccfsi
namcap PKGBUILD sdf-translator-git-*.pkg.tar.zst
```

Regenerate metadata whenever `PKGBUILD` metadata changes:

```bash
makepkg --printsrcinfo > .SRCINFO
```

Review both files and confirm they contain no credentials or personal paths.

## Publish

Copy only `PKGBUILD` and `.SRCINFO` into the separately cloned AUR repository, then:

```bash
git add PKGBUILD .SRCINFO
git commit -m "Initial submission"
git push
```

AUR accepts package updates on its `master` branch. After publishing, verify the user path from a clean directory:

```bash
yay -S sdf-translator-git
```

For a VCS package, do not publish commits that only refresh `pkgver`; `pkgver()` computes the current upstream revision during the build. Publish an AUR update when packaging metadata or the build process changes.
