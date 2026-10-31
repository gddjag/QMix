# QMix 轻麦官网

此目录只保存官网，不包含 QMix 音频引擎、软件源码或安装包。

- 正式域名：`https://qmix.top/`
- 联系作者：`djag@qq.com`
- `index.html` 是可独立打开的原始单页，保留真实软件截图、3D 卡片与操作演示。
- 上线构建会把内嵌图片原样拆出，生成更小的 HTML；不会压缩、重画或修改截图和二维码。

## 本地构建和预览

```sh
python3 QMixWeb/build.py
python3 -m http.server 8877 --bind 127.0.0.1 --directory QMixWeb/dist
```

在浏览器打开 `http://127.0.0.1:8877/`。仅把 `dist` 中的内容部署到公开网站；不要把整个软件仓库作为静态资源目录。

## Cloudflare Pages

- 项目：`qmix-web`。
- Cloudflare 地址：`https://qmix-web.pages.dev/`。
- 已连接下列 GitHub 仓库，推送到生产分支会自动构建部署。
- GitHub 仓库：`gddjag/QMix`，仅公开官网文件，不包含应用程序源码。
- 生产分支：`main`。
- 根目录：`QMixWeb`。
- 构建命令：`python3 build.py`。
- 构建输出目录：`dist`。
- Framework preset：`None`。

若用控制台直接上传，先构建，再上传 `dist` 文件夹或其内容生成的 ZIP。

`qmix.top` 作为 Pages 根域名，需要先在 Cloudflare 添加域名并完成域名服务器设置。不要直接填未知 IP，也不要把未验证的 CNAME 当成绑定成功。

## GitHub 与 R2 下载线路

官网按架构展示 `下载`（R2 主力线路）和 `GitHub 下载`（备用线路）。当前正式版 1.0.3 已发布 Windows x64 / ARM64 与 macOS arm64 / x86_64 安装包，两条线路均已开放；校验值来自同一 Release 的 SHA256SUMS 文件。

每次发布新版本后，必须把每个已发布架构的 R2 与 GitHub 直链、版本号和 SHA-256 同步到 `downloads.json`，运行 `python3 build.py` 检查构建结果，并确认对应下载链接可匿名访问。Cloudflare Pages 会在 `main` 更新后自动部署。尚未发布的架构继续保持禁用；不得把测试包、软件源码或不匹配版本的校验值放入官网。

macOS 卡片保留 Apple 官方首次打开教程；签名和公证状态以对应版本发布说明为准。

## 搜索平台收录

已包含 canonical、robots、Open Graph、软件结构化数据、`robots.txt`、单页 `sitemap.xml` 和 IndexNow 验证文件。站点地图只列出真实首页，不将 `#` 页面锚点当成独立网页。

先确认域名和 HTTPS 可访问，再按各平台登录、验证站点所有权、提交首页和站点地图。提交不保证收录或排名。

| 平台 | 官方入口 | 提交内容 |
| --- | --- | --- |
| Google | https://search.google.com/search-console | 验证 `qmix.top` 后提交 `https://qmix.top/sitemap.xml`，检查首页 URL |
| Bing | https://www.bing.com/webmasters/ | 验证网站、提交 sitemap；也可使用 IndexNow |
| 百度 | https://ziyuan.baidu.com/linksubmit/url/ | 登录并验证网站后提交 `https://qmix.top/`，以账号实际可用功能为准 |
| 搜狗 | https://zhanzhang.sogou.com/index.php/sitelink/index | 提交首页，按平台要求完成验证 |
| 360 | https://zhanzhang.so.com/ | 登录站长平台，按当前入口添加和验证网站 |
| 神马 | https://zhanzhang.sm.cn/ | 添加网站并验证，提交 sitemap |

验证标签和 DNS TXT 值必须从本人平台账号生成，本项目不伪造所有权验证。不要使用已废弃的 Google/Bing sitemap ping 地址。

参考：
- https://developers.google.com/search/docs/crawling-indexing/googlebot
- https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- https://www.indexnow.org/documentation
- https://developers.cloudflare.com/pages/get-started/direct-upload/
- https://developers.cloudflare.com/pages/configuration/custom-domains/
