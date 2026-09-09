# ユーチューブ一覧

登録した YouTube チャンネルの動画を、**公開日順 / 再生回数順**で一覧できる Web ページです。
サーバーは持たず、GitHub Pages ＋ GitHub Actions の無料枠だけで動きます。
**YouTube API キーは不要**（公開RSSフィードだけを使います）。

公開URL: https://git-san-934.github.io/youtube-ichiran/

## 仕組み

```
GitHub Actions（6時間おき ＋ 手動実行）
  └ scripts/update.py
       ├ data/channels.json の各チャンネルの公開RSSを取得（ログイン・APIキー不要）
       │     https://www.youtube.com/feeds/videos.xml?channel_id=UC...
       ├ 各動画の 公開日 / 再生回数 / タイトル / サムネイル を抽出
       └ data/videos.json に「マージ」して commit
            ・既存の動画は消さず、再生回数だけ最新値に更新
            ・フィードは各チャンネル最新15件のみだが、過去分は残るので実行ごとに蓄積
            ・チャンネルごとに最大300件まで保持（古いものから削除）
GitHub Pages（main ブランチをそのまま配信）
  └ index.html + assets/ が videos.json を読んでカード一覧を描画
       ・上部でチャンネルを選択（初期表示は「すべて」）
       ・「公開日が新しい順 / 再生回数が多い順」を切り替え
       ・選んだ条件はこの端末のブラウザに記憶
```

| ファイル | 役割 |
|---|---|
| `index.html`, `assets/` | 画面（HTML / CSS / JavaScript） |
| `data/channels.json` | 登録チャンネル（`handle` / `channel_id` / `name`）。**ここを編集して追加・削除** |
| `data/videos.json` | 動画データ（Actions が自動更新。手で編集しない） |
| `scripts/resolve_channels.py` | `@名` からチャンネルIDと表示名を調べて `channels.json` を補完 |
| `scripts/update.py` | RSS取得 → `videos.json` を更新（標準ライブラリのみ） |
| `.github/workflows/update.yml` | 定期実行の設定 |
| `.github/workflows/resolve-channels.yml` | `channels.json` 変更時にID解決＋即取得 |

## 公開手順（最初の1回だけ）

### 1. GitHub リポジトリを作って push する
1. GitHub で空のリポジトリ `youtube-ichiran` を作成する（README等のチェックは付けない）。
2. 自分のターミナルから push する:
   ```
   cd "C:\Users\a\Desktop\youtube-ichiran"
   git remote add origin https://github.com/git-san-934/youtube-ichiran.git
   git push -u origin main
   ```

### 2. GitHub Pages を有効にする
**Settings → Pages → Source** で「Deploy from a branch」を選び、
ブランチ `main` / フォルダ `/ (root)` を指定して保存する。

### 3. 初回実行
**Actions** タブ →「動画データ更新」→「Run workflow」を1回手動実行する。
数分後、公開URLに動画カードが並びます。以降は6時間おきに自動更新されます。

## チャンネルを追加・削除する

ページ下部の「チャンネルを追加・編集する（GitHub）」リンク、または
`data/channels.json` を直接編集する。

- 追加: `{ "handle": "@あたらしいチャンネル" }` を1行足すだけ
  （`@名` はチャンネルページURL `https://www.youtube.com/@xxxx` の `@xxxx` の部分）
- 削除: その行を消すだけ

commit すると `resolve-channels.yml` が動き、正式なチャンネルID（`UC...`）への変換と
新チャンネルの動画取得（1〜2分）が自動で行われます。

`channels.json` はこのリポジトリの中にあるため、**編集できるのはリポジトリの所有者だけ**です。
第三者がリンクを開いても直接コミットはできず、GitHub 上で「変更の提案（Pull Request）」になり、
所有者が承認しない限りサイトには反映されません。

## ローカルで確認する

```
python scripts/update.py          # videos.json を更新
python -m http.server 8000        # http://localhost:8000 を開く
```

## 注意

再生回数はYouTubeが公開フィードで公表している値で、取得時点のものです（多少の遅延あり）。
ごく新しい動画では再生回数がフィードにまだ含まれず「再生回数不明」と表示されることがあります。
YouTube アカウントや個人情報は一切扱いません。
