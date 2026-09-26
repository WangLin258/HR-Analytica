# -*- coding: utf-8 -*-
"""Simple access-code gate for the Streamlit application."""

import os
import streamlit as st


DEFAULT_ACCESS_CODE = "HR2026"


def require_access() -> None:
    code = os.environ.get("HR_ANALYTICA_ACCESS_CODE", DEFAULT_ACCESS_CODE)
    if not code:
        return
    if st.session_state.get("authorized"):
        return

    st.markdown("### 访问码登录")
    entered = st.text_input("请输入访问码", type="password", key="access_code_input")
    if st.button("进入系统", key="access_code_button"):
        if entered == code:
            st.session_state.authorized = True
            st.rerun()
        else:
            st.error("访问码错误")
    st.stop()