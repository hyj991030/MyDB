import json
from datetime import date

import streamlit as st

DATE_MIN = date(2010, 1, 1)
DATE_MAX = date.today()
from supabase import create_client


def get_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
    except (KeyError, FileNotFoundError):
        st.error(
            "Supabase secrets가 필요합니다.\n\n"
            "로컬: `.streamlit/secrets.toml.example`을 복사해 "
            "`.streamlit/secrets.toml` 작성\n"
            "Cloud: 앱 Settings → Secrets에 동일 형식으로 등록"
        )
        st.stop()
    return create_client(url, key)


@st.cache_resource
def supabase_client():
    return get_supabase()


def episode_label(row):
    return f"{row['season']}부 {row['season_episode']}화 {row.get('title') or ''}"


def parse_comma_json(text):
    text = (text or "").strip()
    if not text:
        return None
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return None
    out = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            out.append(p)
    return out


def format_comma_json(val):
    if val is None:
        return ""
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    if isinstance(val, list):
        return ",".join(str(x) for x in val)
    return str(val)


def next_id(sb, table, pk):
    res = sb.table(table).select(pk).order(pk, desc=True).limit(1).execute()
    rows = res.data or []
    cur = rows[0][pk] if rows else 0
    return int(cur) + 1


def fetch_episodes(sb):
    res = (
        sb.table("episodes")
        .select("episode_id, season, season_episode, title")
        .order("season")
        .order("season_episode")
        .execute()
    )
    return res.data or []


def fetch_characters(sb):
    res = (
        sb.table("characters")
        .select("character_id, name")
        .order("character_id")
        .execute()
    )
    return res.data or []


def fetch_rows(sb, table, pk):
    res = sb.table(table).select("*").order(pk).execute()
    return res.data or []


def episode_options(sb):
    eps = fetch_episodes(sb)
    return {episode_label(e): e["episode_id"] for e in eps}


def character_options(sb):
    chars = fetch_characters(sb)
    return {c["name"]: c["character_id"] for c in chars}


def mode_radio(key):
    return st.radio("모드", ["입력", "수정"], horizontal=True, key=f"mode_{key}")


def draft_key(table):
    return f"draft_{table}"


def clear_draft(table):
    st.session_state.pop(draft_key(table), None)


def clear_form_state(table):
    clear_draft(table)
    st.session_state.pop(f"loaded_{table}", None)


def get_draft(table):
    return st.session_state.get(draft_key(table), {})


def save_draft(table, data):
    st.session_state[draft_key(table)] = data


def draft_val(table, key, loaded, default=None):
    draft = get_draft(table)
    if key in draft and draft[key] is not None:
        return draft[key]
    if loaded and loaded.get(key) is not None:
        return loaded[key]
    return default


def render_reset_button(table):
    if st.button("초기화", key=f"reset_{table}"):
        clear_form_state(table)
        st.rerun()


def render_edit_loader(sb, table, pk, labels_rows):
    if not labels_rows:
        st.info("등록된 항목이 없습니다.")
        return None
    labels = [x[0] for x in labels_rows]
    ids = [x[1] for x in labels_rows]
    idx = st.selectbox("항목", range(len(labels)), format_func=lambda i: labels[i], key=f"pick_{table}")
    if st.button("불러오기", key=f"load_{table}"):
        row = sb.table(table).select("*").eq(pk, ids[idx]).single().execute().data
        st.session_state[f"loaded_{table}"] = row
        clear_draft(table)
        st.rerun()
    return st.session_state.get(f"loaded_{table}")


def tab_episodes(sb):
    st.subheader("회차")
    mode = mode_radio("episodes")
    pk = "episode_id"

    loaded = None
    if mode == "입력":
        st.markdown(f"**{pk}:** {next_id(sb, 'episodes', pk)}")
    else:
        rows = fetch_rows(sb, "episodes", pk)
        loaded = render_edit_loader(
            sb, "episodes", pk,
            [(f"{r[pk]}: {episode_label(r)}", r[pk]) for r in rows],
        )
        if loaded is None and not rows:
            return
        if loaded:
            st.markdown(f"**{pk}:** {loaded[pk]}")
        else:
            st.info("항목을 선택한 뒤 「불러오기」를 누르세요.")
            return

    render_reset_button("episodes")

    def val(key, default=None):
        return draft_val("episodes", key, loaded, default)

    ud = val("upload_date")
    if isinstance(ud, str):
        ud = date.fromisoformat(ud[:10])
    if ud is None:
        ud = DATE_MAX
    if ud < DATE_MIN:
        ud = DATE_MIN
    elif ud > DATE_MAX:
        ud = DATE_MAX

    with st.form("form_episodes"):
        season = st.number_input("season (시즌)", min_value=0, step=1, value=int(val("season") or 1))
        season_episode = st.number_input(
            "season_episode (회차)", min_value=0, step=1, value=int(val("season_episode") or 1)
        )
        title = st.text_input("title (제목)", value=val("title") or "")
        upload_date = st.date_input(
            "upload_date (업로드일)",
            value=ud,
            min_value=DATE_MIN,
            max_value=DATE_MAX,
        )
        authors_note = st.text_area("authors_note (작가의 말)", value=val("authors_note") or "")
        plot_summary = st.text_area("plot_summary (줄거리)", value=val("plot_summary") or "")
        main_events = st.text_area("main_events (세부 내용)", value=val("main_events") or "")
        submitted = st.form_submit_button("수정 저장" if mode == "수정" else "저장")

    if submitted:
        if not title.strip():
            st.warning("제목을 입력해 주세요.")
            return
        payload = {
            "season": int(season),
            "season_episode": int(season_episode),
            "title": title.strip(),
            "upload_date": upload_date.isoformat(),
            "authors_note": authors_note.strip() or None,
            "plot_summary": plot_summary.strip() or None,
            "main_events": main_events.strip() or None,
        }
        try:
            if mode == "수정":
                eid = loaded[pk]
                sb.table("episodes").update(payload).eq(pk, eid).execute()
                st.session_state["loaded_episodes"] = {**loaded, **payload}
                st.success(f"회차 {eid}번 수정 완료")
            else:
                payload[pk] = next_id(sb, "episodes", pk)
                sb.table("episodes").insert(payload).execute()
                st.success(f"회차 {payload[pk]}번 저장 완료")
            save_draft("episodes", payload)
            st.rerun()
        except Exception as e:
            st.error(str(e))


def tab_characters(sb):
    st.subheader("캐릭터")
    mode = mode_radio("characters")
    pk = "character_id"

    loaded = None
    if mode == "입력":
        st.markdown(f"**{pk}:** {next_id(sb, 'characters', pk)}")
    else:
        rows = fetch_rows(sb, "characters", pk)
        loaded = render_edit_loader(
            sb, "characters", pk,
            [(f"{r[pk]}: {r.get('name') or ''}", r[pk]) for r in rows],
        )
        if loaded is None and not rows:
            return
        if loaded:
            st.markdown(f"**{pk}:** {loaded[pk]}")
        else:
            st.info("항목을 선택한 뒤 「불러오기」를 누르세요.")
            return

    render_reset_button("characters")

    def val(key, default=""):
        v = draft_val("characters", key, loaded, default)
        if key == "appearance_episodes" and v not in (None, ""):
            return format_comma_json(v)
        return v if v is not None else default

    with st.form("form_characters"):
        name = st.text_input("name (이름)", value=val("name"))
        aliases = st.text_input("aliases (별명)", value=val("aliases"))
        appearance_episodes = st.text_input(
            "appearance_episodes (출연회차)",
            value=val("appearance_episodes"),
            help="쉼표(,)로 구분, 띄어쓰기 없이",
        )
        appearance_desc = st.text_area("appearance_desc (외형)", value=val("appearance_desc"))
        personality_traits = st.text_area(
            "personality_traits (성격)", value=val("personality_traits")
        )
        submitted = st.form_submit_button("수정 저장" if mode == "수정" else "저장")

    if submitted:
        if not name.strip():
            st.warning("이름을 입력해 주세요.")
            return
        payload = {
            "name": name.strip(),
            "aliases": aliases.strip() or None,
            "appearance_episodes": parse_comma_json(appearance_episodes),
            "appearance_desc": appearance_desc.strip() or None,
            "personality_traits": personality_traits.strip() or None,
        }
        try:
            if mode == "수정":
                eid = loaded[pk]
                sb.table("characters").update(payload).eq(pk, eid).execute()
                st.session_state["loaded_characters"] = {**loaded, **payload}
                st.success(f"캐릭터 {eid}번 수정 완료")
            else:
                payload[pk] = next_id(sb, "characters", pk)
                sb.table("characters").insert(payload).execute()
                st.success(f"캐릭터 {payload[pk]}번 저장 완료")
            draft_payload = {
                **payload,
                "appearance_episodes": appearance_episodes.strip(),
            }
            save_draft("characters", draft_payload)
            st.rerun()
        except Exception as e:
            st.error(str(e))


def tab_dialogues(sb):
    st.subheader("대사")
    mode = mode_radio("dialogues")
    pk = "dialogue_id"
    ep_opts = episode_options(sb)
    ch_opts = character_options(sb)

    if not ep_opts:
        st.warning("먼저 회차를 등록하세요.")
    if not ch_opts:
        st.warning("먼저 캐릭터를 등록하세요.")

    loaded = None
    if mode == "입력":
        st.markdown(f"**{pk}:** {next_id(sb, 'dialogues', pk)}")
    else:
        rows = fetch_rows(sb, "dialogues", pk)
        eps = {e["episode_id"]: episode_label(e) for e in fetch_episodes(sb)}
        chs = {c["character_id"]: c["name"] for c in fetch_characters(sb)}
        items = []
        for r in rows:
            ep = eps.get(r.get("episode_id"), "?")
            nm = chs.get(r.get("character_id"), "?")
            preview = (r.get("script") or "")[:36]
            items.append((f"{r[pk]}: [{ep}] {nm} #{r.get('cut_order')} {preview}", r[pk]))
        loaded = render_edit_loader(sb, "dialogues", pk, items)
        if loaded is None and not rows:
            return
        if loaded:
            st.markdown(f"**{pk}:** {loaded[pk]}")
        else:
            st.info("항목을 선택한 뒤 「불러오기」를 누르세요.")
            return

    render_reset_button("dialogues")

    def ep_default():
        eid = draft_val("dialogues", "episode_id", loaded, None)
        if eid is None:
            return 0
        labels = list(ep_opts.keys())
        ids = list(ep_opts.values())
        return labels.index(next(l for l, i in zip(labels, ids) if i == eid)) if eid in ids else 0

    def ch_default():
        cid = draft_val("dialogues", "character_id", loaded, None)
        if cid is None:
            return 0
        labels = list(ch_opts.keys())
        ids = list(ch_opts.values())
        return labels.index(next(l for l, i in zip(labels, ids) if i == cid)) if cid in ids else 0

    with st.form("form_dialogues"):
        ep_label = st.selectbox(
            "episode_id (회차)",
            list(ep_opts.keys()) if ep_opts else ["(없음)"],
            index=ep_default() if ep_opts else 0,
            disabled=not ep_opts,
        )
        ch_label = st.selectbox(
            "character_id (캐릭터)",
            list(ch_opts.keys()) if ch_opts else ["(없음)"],
            index=ch_default() if ch_opts else 0,
            disabled=not ch_opts,
        )
        script = st.text_area(
            "script (대사)",
            value=draft_val("dialogues", "script", loaded, "") or "",
            height=160,
        )
        cut_order = st.number_input(
            "cut_order (컷 위치)",
            min_value=0,
            step=1,
            value=int(draft_val("dialogues", "cut_order", loaded, 1) or 1),
        )
        submitted = st.form_submit_button("수정 저장" if mode == "수정" else "저장")

    if submitted:
        if not ep_opts or not ch_opts:
            st.warning("회차와 캐릭터가 필요합니다.")
            return
        if not script.strip():
            st.warning("대사를 입력해 주세요.")
            return
        payload = {
            "episode_id": ep_opts[ep_label],
            "character_id": ch_opts[ch_label],
            "script": script.strip(),
            "cut_order": int(cut_order),
        }
        try:
            if mode == "수정":
                eid = loaded[pk]
                sb.table("dialogues").update(payload).eq(pk, eid).execute()
                st.session_state["loaded_dialogues"] = {**loaded, **payload}
                st.success(f"대사 {eid}번 수정 완료")
            else:
                payload[pk] = next_id(sb, "dialogues", pk)
                payload["embedding"] = None
                sb.table("dialogues").insert(payload).execute()
                st.success(f"대사 {payload[pk]}번 저장 완료")
            save_draft("dialogues", payload)
            st.rerun()
        except Exception as e:
            st.error(str(e))


def tab_terminology(sb):
    st.subheader("용어")
    mode = mode_radio("terminology")
    pk = "term_id"
    ep_opts = episode_options(sb)

    loaded = None
    if mode == "입력":
        st.markdown(f"**{pk}:** {next_id(sb, 'terminology', pk)}")
    else:
        rows = fetch_rows(sb, "terminology", pk)
        loaded = render_edit_loader(
            sb, "terminology", pk,
            [
                (
                    f"{r[pk]}: {r.get('term_name') or ''}"
                    + (f" ({r['category']})" if r.get("category") else ""),
                    r[pk],
                )
                for r in rows
            ],
        )
        if loaded is None and not rows:
            return
        if loaded:
            st.markdown(f"**{pk}:** {loaded[pk]}")
        else:
            st.info("항목을 선택한 뒤 「불러오기」를 누르세요.")
            return

    render_reset_button("terminology")

    def ep_idx():
        eid = draft_val("terminology", "first_mentioned", loaded, None)
        if eid is None or not ep_opts:
            return 0
        ids = list(ep_opts.values())
        return ids.index(eid) if eid in ids else 0

    with st.form("form_terminology"):
        term_name = st.text_input(
            "term_name (명칭)", value=draft_val("terminology", "term_name", loaded, "") or ""
        )
        category = st.text_input(
            "category (분류)", value=draft_val("terminology", "category", loaded, "") or ""
        )
        official_desc = st.text_area(
            "official_desc (설명)",
            value=draft_val("terminology", "official_desc", loaded, "") or "",
        )
        ep_label = st.selectbox(
            "first_mentioned (첫 등장)",
            list(ep_opts.keys()) if ep_opts else ["(없음)"],
            index=ep_idx() if ep_opts else 0,
            disabled=not ep_opts,
        )
        submitted = st.form_submit_button("수정 저장" if mode == "수정" else "저장")

    if submitted:
        if not term_name.strip():
            st.warning("명칭을 입력해 주세요.")
            return
        if not ep_opts:
            st.warning("회차를 먼저 등록하세요.")
            return
        payload = {
            "term_name": term_name.strip(),
            "category": category.strip() or None,
            "official_desc": official_desc.strip() or None,
            "first_mentioned": ep_opts[ep_label],
        }
        try:
            if mode == "수정":
                eid = loaded[pk]
                sb.table("terminology").update(payload).eq(pk, eid).execute()
                st.session_state["loaded_terminology"] = {**loaded, **payload}
                st.success(f"용어 {eid}번 수정 완료")
            else:
                payload[pk] = next_id(sb, "terminology", pk)
                sb.table("terminology").insert(payload).execute()
                st.success(f"용어 {payload[pk]}번 저장 완료")
            save_draft("terminology", payload)
            st.rerun()
        except Exception as e:
            st.error(str(e))


def tab_etc(sb):
    st.subheader("기타")
    mode = mode_radio("etc")
    pk = "etc_id"

    loaded = None
    if mode == "입력":
        st.markdown(f"**{pk}:** {next_id(sb, 'etc', pk)}")
    else:
        rows = fetch_rows(sb, "etc", pk)
        loaded = render_edit_loader(
            sb, "etc", pk,
            [
                (
                    f"{r[pk]}: {r.get('etc_name') or ''}"
                    + (f" [{r['etc_type']}]" if r.get("etc_type") else ""),
                    r[pk],
                )
                for r in rows
            ],
        )
        if loaded is None and not rows:
            return
        if loaded:
            st.markdown(f"**{pk}:** {loaded[pk]}")
        else:
            st.info("항목을 선택한 뒤 「불러오기」를 누르세요.")
            return

    render_reset_button("etc")

    with st.form("form_etc"):
        etc_type = st.text_input(
            "etc_type (분류)", value=draft_val("etc", "etc_type", loaded, "") or ""
        )
        etc_name = st.text_input(
            "etc_name (명칭)", value=draft_val("etc", "etc_name", loaded, "") or ""
        )
        etc_desc = st.text_area(
            "etc_desc (설명)", value=draft_val("etc", "etc_desc", loaded, "") or ""
        )
        submitted = st.form_submit_button("수정 저장" if mode == "수정" else "저장")

    if submitted:
        if not etc_name.strip():
            st.warning("명칭을 입력해 주세요.")
            return
        payload = {
            "etc_type": etc_type.strip() or None,
            "etc_name": etc_name.strip(),
            "etc_desc": etc_desc.strip() or None,
        }
        try:
            if mode == "수정":
                eid = loaded[pk]
                sb.table("etc").update(payload).eq(pk, eid).execute()
                st.session_state["loaded_etc"] = {**loaded, **payload}
                st.success(f"기타 {eid}번 수정 완료")
            else:
                payload[pk] = next_id(sb, "etc", pk)
                sb.table("etc").insert(payload).execute()
                st.success(f"기타 {payload[pk]}번 저장 완료")
            save_draft("etc", payload)
            st.rerun()
        except Exception as e:
            st.error(str(e))


def main():
    st.set_page_config(page_title="MyDB 입력", page_icon="📚", layout="centered")
    st.title("MyDB 데이터 입력")
    st.caption("Supabase · Streamlit")

    sb = supabase_client()

    t1, t2, t3, t4, t5 = st.tabs(["회차", "캐릭터", "대사", "용어", "기타"])
    with t1:
        tab_episodes(sb)
    with t2:
        tab_characters(sb)
    with t3:
        tab_dialogues(sb)
    with t4:
        tab_terminology(sb)
    with t5:
        tab_etc(sb)


if __name__ == "__main__":
    main()
