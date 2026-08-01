# Arch / AUR 打包

`PKGBUILD` 遵循 Arch 版本控制系统软件包规范，并将 Git 最新修订安装为 `sdf-translator-git`。

上游源码地址已经配置为 <https://github.com/GoKo-Son626/sdf>。

首次发布 AUR 前：

1. 在 <https://aur.archlinux.org/register> 注册 AUR 账户，并在账户设置中添加本机 SSH 公钥。
2. 确认 `sdf-translator-git` 名称尚未被占用，然后克隆独立 AUR 仓库：

   ```bash
   git clone ssh://aur@aur.archlinux.org/sdf-translator-git.git
   ```

3. 将本目录 `PKGBUILD` 顶部的维护者注释替换为真实 AUR 维护者姓名和邮箱。
4. 在本目录构建并检查软件包：

   ```bash
   makepkg -Ccfsi
   namcap PKGBUILD sdf-translator-git-*.pkg.tar.zst
   ```

5. 每次修改 `PKGBUILD` 元数据后重新生成：

   ```bash
   makepkg --printsrcinfo > .SRCINFO
   ```

6. 将 `PKGBUILD` 和 `.SRCINFO` 复制到刚才克隆的 AUR 仓库，然后提交并推送：

   ```bash
   git add PKGBUILD .SRCINFO
   git commit -m "首次发布 sdf-translator-git"
   git push
   ```

7. 发布后运行 `yay -S sdf-translator-git` 做一次从 AUR 安装的最终验证。

本项目普通源码仓库的 `main` 分支与 AUR 软件包仓库是两个独立的 Git 仓库。
