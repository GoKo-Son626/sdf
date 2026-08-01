# Arch / AUR packaging

`PKGBUILD` follows the Arch VCS package format and installs the latest Git revision as `sdf-translator-git`.

Before publishing the first AUR revision:

1. Publish this source repository on GitHub.
2. Replace `OWNER` in `PKGBUILD` with the GitHub account or organization.
3. Replace the maintainer comment with the real AUR maintainer name and email.
4. Build and inspect the package locally:

   ```bash
   makepkg -Ccfsi
   namcap PKGBUILD sdf-translator-git-*.pkg.tar.zst
   ```

5. Regenerate metadata after every PKGBUILD metadata change:

   ```bash
   makepkg --printsrcinfo > .SRCINFO
   ```

6. Copy `PKGBUILD` and `.SRCINFO` into the separately cloned AUR repository, commit, and push its `master` branch.

Do not publish while `OWNER` remains in the URL. The repository's normal `main` branch and the AUR package repository are separate Git repositories.
