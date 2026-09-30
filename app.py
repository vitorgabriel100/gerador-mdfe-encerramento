    if "ins_agora" not in st.session_state:
        st.session_state["ins_agora"] = gerar_instante_evento().replace(microsecond=0)
    agora = st.session_state["ins_agora"]
    motivo = st.selectbox(
        "Motivo do insucesso", list(MOTIVOS_INSUCESSO),
        format_func=lambda codigo: f"{codigo} — {MOTIVOS_INSUCESSO[codigo]}",
        key="ins_motivo",
    )
    justificativa = st.text_area(
        "Justificativa do insucesso", max_chars=256,
        help="Explique o motivo com 15 a 256 caracteres.", key="ins_justificativa",
    )
    st.caption(f"{len(justificativa.strip())}/256 caracteres (mínimo 15).")
    evento_agora = st.checkbox(
        "Usar data e hora da geração para o evento", value=True, key="ins_evento_agora"
    )
    col1, col2 = st.columns(2)
    with col1:
        data_evento = st.date_input(
            "Data do evento", value=agora.date(), key="ins_data_evento", disabled=evento_agora
        )
        hora_evento_texto = st.text_input(
            "Hora do evento (HH:MM:SS)", value=agora.strftime("%H:%M:%S"),
            key="ins_hora_evento", disabled=evento_agora,
        )
    with col2:
        data_tentativa = st.date_input(
            "Data da tentativa de entrega", value=agora.date(), key="ins_data_tentativa"
        )
        hora_tentativa_texto = st.text_input(
            "Hora da tentativa de entrega (HH:MM:SS)", value="", placeholder="18:15:00",
            key="ins_hora_tentativa", help="Informe o horário real da tentativa do motorista.",
        )
    if not hora_tentativa_texto.strip():
        st.session_state.pop("ins_resultado", None)
        st.info("Confira a data e informe o horário real da tentativa de entrega.")
        return
    try:
        hora_evento = datetime.strptime(hora_evento_texto, "%H:%M:%S").time()
        hora_tentativa = datetime.strptime(hora_tentativa_texto, "%H:%M:%S").time()
    except ValueError:
        st.session_state.pop("ins_resultado", None)
        st.error("Informe as horas no formato HH:MM:SS, por exemplo 18:15:00.")
        return
    instante = datetime.combine(data_evento, hora_evento, tzinfo=FUSO_BR)
    tentativa = datetime.combine(data_tentativa, hora_tentativa, tzinfo=FUSO_BR)
    entradas = (chave, cnpj, motivo, justificativa, None if evento_agora else instante, tentativa)
    # Não oferece para download um XML antigo depois de alterar o formulário.
    if st.session_state.get("ins_entradas") != entradas:
        st.session_state.pop("ins_resultado", None)
    if st.button("Gerar XML de Insucesso", key="ins_gerar", use_container_width=True):
        try:
            xml_final = montar_xml_insucesso(
                chave, cnpj, motivo, justificativa,
                gerar_instante_evento() if evento_agora else instante, tentativa,
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["ins_entradas"] = entradas
            st.session_state["ins_resultado"] = xml_final
    if "ins_resultado" in st.session_state:
        xml_final = st.session_state["ins_resultado"]
        nome_arquivo = gerar_nome_arquivo(chave, "ins")
        st.success("XML de insucesso gerado com sucesso.")
        st.write(f"**Arquivo:** `{nome_arquivo}`")
        st.code(xml_final, language="xml")
        st.download_button(
            "Baixar XML de Insucesso", data=xml_final.encode("utf-8"),
            file_name=nome_arquivo, mime="application/xml",
            key="ins_download", use_container_width=True,
        )


def main() -> None:
    st.set_page_config(
        page_title="Gerador XML MDF-e e CT-e",
        layout="centered"
    )

    st.title("Gerador de XML MDF-e e CT-e")

    st.write(
        "Gere eventos de encerramento e cancelamento de MDF-e "
        "ou de insucesso na entrega de CT-e."
    )

    encerramento, cancelamento, insucesso = st.tabs(
        ["Encerramento MDF-e", "Cancelamento MDF-e", "Insucesso CT-e"]
    )

    st.divider()

    with encerramento:
        tela_encerramento()

    with cancelamento:
        tela_cancelamento()

    with insucesso:
        tela_insucesso()


if __name__ == "__main__":
    main()
