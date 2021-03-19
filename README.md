# meteo-template

気象要素を都道府県別・気象要素別の元データのファイルを統合し、３次メッシュ別に変換するプロセス。

データ量の観点から、年ごとに新しいレポジトリーを作成します。このレポジトリーをテンプレート
として使って、データを入れると GitHub Actions でそのデータの元に３次メッシュ別の静的
ファイルを生成し、 GitHub Pages に公開します。

## このテンプレートの使い方

1. GitHub から新しいレポジトリーを作ります
	1. Repository template にこのレポジトリーを選択してください（ `agro-env/meteo-template` ）
	2. Owner は `agro-env` を設定し、 Repository name は `meteo-YYYY` に設定します（ `YYYY` に4桁の西暦年を置き換えてください）
	3. 公開設定は `Public` に設定し、 `Include all branches` にチェックが入ってることを確認してください。
2. 新しく作られたレポジトリーに元データをアップロードします
	1. `meteo-YYYY` をパソコンに clone します。（ `git clone git@github.com:agro-env/meteo-YYYY` )
	2. `raw_data` のディレクトリにテンプレートのように、 `pr` `sd` `sr` ... などのディレクトリをコピーしてください。（テンプレートに入ってる既存の空ディレクトリーを上書きしてください）
	3. コミットし、レポジトリーにプッシュします。（ `git add . && git commit -m "Add data for year YYYY" && git push` ）
3. GitHub Actions の様子を見る
	1. GitHub のページ上の "Actions" というタブをクリックすると "All workflows" に処理中プロセスが見れます
4. GitHub Pages を公開する（ステップ1で `Include all branches` にチェックが入ってる場合、下記を手順は不要です）
	1. 処理が完了した後、 "Settings" のタブをクリックします。
	2. ページ下部にスクロールし（ "GitHub Pages" のセクションまで）、Source のブランチを `gh-pages` に設定します。ディレクトリは `/ (root)` に設定します。
	3. "Save" ボタンを押します。

GitHub Pages を公開したら公開作業が開始されます。大体 10 ~ 20 分で Settings の画面に記載されている URL に公開されます。

## 変換をローカルで実行する

変換をローカルで実行したい場合は下記の環境が必要です

* Python 3.7 以上 (3.8.8 の環境で開発されています)

環境の初期設定は下記の該当するOSをクリックし、参考にしてください。

<details><summary>UNIX (Linux / macOS)</summary>
<p>

```shell
$ python3 -m venv .venv
$ . .venv/bin/activate
$ pip install -U pip
$ pip install -r requirements.txt
```

</p>
</details>

<details><summary>Windows (PowerShell)</summary>
<p>

```powershell
> python -m venv .venv
> . .\.venv\Scripts\Activate.ps1
> pip install -U pip
> pip install -r requirements.txt
```

`Activate.ps1` を実行するところで権限エラーになる場合は、下記のコマンドを実行しもう一度試してください。

```powershell
Set-ExecutionPolicy -Scope CurrentUser Unrestricted
```

</p>
</details>

環境構築後、 `transform.py` スクリプトが利用可能になります。

```
python transform.py [1年分の気象要素データが入ったディレクトリー]
```

出力は同ディレクトリーの `out` に入ります。

出力を都道府県に絞る場合は

```
python transform.py -k 0A,12,36 ../data/2000
```

の様にカンマ区切りで指定できます。

並列処理を無効化する場合は `-p` を使用して並列処理のプロセス数を1に設定してください。

```
python transform.py -p 1 ../data/2000
```

## 注意点

このスクリプトは6要素（ `pr sd sr tm tn tx` ）が存在する前提で作られています。 `raw_data` にファイルが不足している場合はエラーになる場合があります。
