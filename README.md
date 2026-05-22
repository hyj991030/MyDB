# MyDB Streamlit (Cloud 배포용)

이 폴더만 GitHub 저장소로 올려 [Streamlit Community Cloud](https://share.streamlit.io)에 배포하면 됩니다.

## 폴더 구성

```
streamlit_cloud/
  streamlit_app.py      ← Main file path
  requirements.txt
  .streamlit/
    secrets.toml.example
  .gitignore
  README.md
```

## 로컬 실행

```powershell
cd streamlit_cloud
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

`secrets.toml`에 Supabase URL·키 입력 후:

```powershell
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## GitHub + Streamlit Cloud

```powershell
cd streamlit_cloud
git init
git add .
git status
```

`secrets.toml`이 목록에 없어야 합니다.

```powershell
git commit -m "MyDB Streamlit app"
git remote add origin https://github.com/USER/REPO.git
git push -u origin main
```

Cloud에서 **New app** → 저장소 선택 → **Main file:** `streamlit_app.py`  
**Secrets**에 `secrets.toml`과 같은 내용 등록 (GitHub에 넣지 않음).

공개 배포 시 **anon public** 키 + Supabase RLS 권장.
