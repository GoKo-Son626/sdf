# Arch / AUR packaging

`PKGBUILD` follows the Arch VCS package format and installs the latest Git revision as `sdf-translator-git`.

The upstream source is configured as <https://github.com/GoKo-Son626/sdf>.

Before publishing the first AUR revision:

1. Replace the maintainer comment with the real AUR maintainer name and email.
2. Build and inspect the package locally:

   ```bash
   makepkg -Ccfsi
   namcap PKGBUILD sdf-translator-git-*.pkg.tar.zst
   ```

3. Regenerate metadata after every PKGBUILD metadata change:

   ```bash
   makepkg --printsrcinfo > .SRCINFO
   ```

4. Copy `PKGBUILD` and `.SRCINFO` into the separately cloned AUR repository, commit, and push its `master` branch.

The repository's normal `main` branch and the AUR package repository are separate Git repositories.
