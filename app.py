from __future__ import annotations

import re
import hashlib
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import streamlit as st


FUSO_BR = timezone(timedelta(hours=-3))


def limpar_numeros(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def validar_chave_mdfe(chave: str) -> bool:
    return bool(re.fullmatch(r"\d{44}", chave))


def validar_protocolo(protocolo: str) -> bool:
    return bool(re.fullmatch(r"\d{1,20}", protocolo))


def gerar_instante_evento() -> datetime:
    return datetime.now(FUSO_BR)


def gerar_dh_evento(instante: datetime) -> str:
    return instante.isoformat(timespec="seconds")


def gerar_dt_enc(instante: datetime) -> str:
    return instante.strftime("%Y-%m-%d")


def gerar_id_evento(chave: str, tp_evento: str) -> str:
    return f"ID{tp_evento}{chave}01"


def gerar_nome_arquivo(chave: str, tipo_evento: str) -> str:
    return f"env_{chave}{tipo_evento}-ped-evt.xml"


def nome_tag(elem: ET.Element) -> str:
    if "}" in elem.tag:
        return elem.tag.split("}", 1)[1]
    return elem.tag


def buscar_primeiro_texto(root: ET.Element, tag: str) -> str:
    for elem in root.iter():
        if nome_tag(elem) == tag and elem.text:
            return elem.text.strip()
    return ""


def extrair_chave_mdfe(root: ET.Element) -> str:
    chave = limpar_numeros(buscar_primeiro_texto(root, "chMDFe"))

    if validar_chave_mdfe(chave):
        return chave

    for elem in root.iter():
        id_attr = elem.attrib.get("Id", "")

        # Exemplo: Id="MDFe352605..."
        match_mdfe = re.search(r"MDFe(\d{44})", id_attr)
        if match_mdfe:
            return match_mdfe.group(1)

        # Exemplo: Id="ID110111352605...01"
        match_evento = re.search(r"ID\d{6}(\d{44})\d{2}", id_attr)
        if match_evento:
            return match_evento.group(1)

    return ""


def extrair_dados_do_xml(xml_bytes: bytes) -> dict:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"XML inválido: {e}")

    chave = extrair_chave_mdfe(root)

    protocolo = limpar_numeros(buscar_primeiro_texto(root, "nProt"))
    cnpj = limpar_numeros(buscar_primeiro_texto(root, "CNPJ"))
    cuf = limpar_numeros(buscar_primeiro_texto(root, "cUF"))
    cmun = limpar_numeros(buscar_primeiro_texto(root, "cMun"))

    # Fallback usando a própria chave.
    if validar_chave_mdfe(chave):
        if not cuf:
            cuf = chave[:2]

        if not cnpj:
            cnpj = chave[6:20]

    return {
        "chave": chave,
        "protocolo": protocolo,
        "cnpj": cnpj,
        "cuf": cuf,
        "cmun": cmun,
    }


def validar_dados_encerramento(dados: dict) -> None:
    if not validar_chave_mdfe(dados["chave"]):
        raise ValueError("Não foi possível encontrar uma chave MDF-e válida com 44 dígitos.")

    if not validar_protocolo(dados["protocolo"]):
        raise ValueError("Não foi possível encontrar um protocolo válido no XML.")

    if len(dados["cnpj"]) != 14:
        raise ValueError("Não foi possível encontrar um CNPJ válido no XML.")

    if len(dados["cuf"]) != 2:
        raise ValueError("Não foi possível encontrar um cUF válido no XML.")

    if len(dados["cmun"]) != 7:
        raise ValueError("Não foi possível encontrar um cMun válido no XML.")


def validar_dados_cancelamento(dados: dict) -> None:
    if not validar_chave_mdfe(dados["chave"]):
        raise ValueError("Informe uma chave MDF-e válida com 44 dígitos.")

    if not validar_protocolo(dados["protocolo"]):
        raise ValueError("Informe um nProt válido.")

    if len(dados["cnpj"]) != 14:
        raise ValueError("Informe um CNPJ válido com 14 dígitos.")

    if len(dados["cuf"]) != 2:
        raise ValueError("Informe um cUF / cOrgao válido com 2 dígitos.")


def montar_xml_encerramento(
    chave: str,
    cnpj: str,
    cuf: str,
    protocolo: str,
    cmun: str,
    instante: datetime
) -> str:
    return f"""<eventoMDFe versao="3.00" xmlns="http://www.portalfiscal.inf.br/mdfe">
  <infEvento Id="{gerar_id_evento(chave, "110112")}">
    <cOrgao>{cuf}</cOrgao>
    <tpAmb>1</tpAmb>
    <CNPJ>{cnpj}</CNPJ>
    <chMDFe>{chave}</chMDFe>
    <dhEvento>{gerar_dh_evento(instante)}</dhEvento>
    <tpEvento>110112</tpEvento>
    <nSeqEvento>01</nSeqEvento>
    <detEvento versaoEvento="3.00">
      <evEncMDFe>
        <descEvento>Encerramento</descEvento>
        <nProt>{protocolo}</nProt>
        <dtEnc>{gerar_dt_enc(instante)}</dtEnc>
        <cUF>{cuf}</cUF>
        <cMun>{cmun}</cMun>
      </evEncMDFe>
    </detEvento>
  </infEvento>
</eventoMDFe>"""


def montar_xml_cancelamento(
    chave: str,
    cnpj: str,
    cuf: str,
    protocolo: str,
    justificativa: str,
    instante: datetime
) -> str:
    justificativa_xml = escape(justificativa.strip())

    return f"""<eventoMDFe versao="3.00" xmlns="http://www.portalfiscal.inf.br/mdfe">
  <infEvento Id="{gerar_id_evento(chave, "110111")}">
    <cOrgao>{cuf}</cOrgao>
    <tpAmb>1</tpAmb>
    <CNPJ>{cnpj}</CNPJ>
    <chMDFe>{chave}</chMDFe>
    <dhEvento>{gerar_dh_evento(instante)}</dhEvento>
    <tpEvento>110111</tpEvento>
    <nSeqEvento>01</nSeqEvento>
    <detEvento versaoEvento="3.00">
      <evCancMDFe>
        <descEvento>Cancelamento</descEvento>
        <nProt>{protocolo}</nProt>
        <xJust>{justificativa_xml}</xJust>
      </evCancMDFe>
    </detEvento>
  </infEvento>
</eventoMDFe>"""


def mostrar_resultado(
    dados: dict,
    nome_arquivo: str,
    xml_final: str,
    mostrar_cmun: bool = True
) -> None:
    st.success("XML gerado com sucesso.")

    st.subheader("Dados utilizados")
    st.write(f"**Chave:** `{dados['chave']}`")
    st.write(f"**Protocolo:** `{dados['protocolo']}`")
    st.write(f"**CNPJ:** `{dados['cnpj']}`")
    st.write(f"**cUF / cOrgao:** `{dados['cuf']}`")

    if mostrar_cmun:
        st.write(f"**cMun:** `{dados['cmun']}`")

    st.write(f"**Arquivo:** `{nome_arquivo}`")

    st.subheader("Preview do XML")
    st.code(xml_final, language="xml")

    st.download_button(
        label="Baixar XML",
        data=xml_final.encode("utf-8"),
        file_name=nome_arquivo,
        mime="application/xml",
        use_container_width=True
    )


def tela_encerramento() -> None:
    st.subheader("XML de Encerramento")

    st.info(
        "Para gerar o encerramento, envie o XML do MDF-e com protocolo. "
        "O sistema tentará extrair automaticamente chave, protocolo, CNPJ, cUF e cMun."
    )

    xml_file = st.file_uploader(
        "Envie o XML do MDF-e",
        type=["xml"],
        key="xml_encerramento"
    )

    if st.button("Gerar XML de Encerramento", use_container_width=True):
        if xml_file is None:
            st.error("Envie o XML do MDF-e para gerar o encerramento.")
            return

        try:
            dados = extrair_dados_do_xml(xml_file.getvalue())
            validar_dados_encerramento(dados)
        except Exception as e:
            st.error(str(e))
            return

        instante = gerar_instante_evento()

        xml_final = montar_xml_encerramento(
            chave=dados["chave"],
            cnpj=dados["cnpj"],
            cuf=dados["cuf"],
            protocolo=dados["protocolo"],
            cmun=dados["cmun"],
            instante=instante
        )

        nome_arquivo = gerar_nome_arquivo(dados["chave"], "enc")

        mostrar_resultado(
            dados=dados,
            nome_arquivo=nome_arquivo,
            xml_final=xml_final,
            mostrar_cmun=True
        )


def tela_cancelamento() -> None:
    st.subheader("XML de Cancelamento")

    st.info(
        "Para gerar o cancelamento, você pode enviar o XML do MDF-e ou preencher os dados manualmente. "
        "O XML não precisa obrigatoriamente ser processado. Se algum dado não vier no XML, preencha abaixo."
    )

    xml_file = st.file_uploader(
        "Envie o XML do MDF-e, se tiver",
        type=["xml"],
        key="xml_cancelamento"
    )

    dados_xml = {
        "chave": "",
        "protocolo": "",
        "cnpj": "",
        "cuf": "",
        "cmun": "",
    }

    if xml_file is not None:
        try:
            dados_xml = extrair_dados_do_xml(xml_file.getvalue())
            st.success("XML lido com sucesso. Confira ou complete os dados abaixo.")
        except Exception as e:
            st.error(str(e))
            return

    st.markdown("### Dados para o cancelamento")

    chave_manual = st.text_input(
        "Chave do MDF-e",
        value=dados_xml["chave"],
        placeholder="44 dígitos"
    )

    protocolo_manual = st.text_input(
        "nProt / Protocolo",
        value=dados_xml["protocolo"],
        placeholder="Informe o protocolo do MDF-e"
    )

    col1, col2 = st.columns(2)

    with col1:
        cnpj_manual = st.text_input(
            "CNPJ do emitente",
            value=dados_xml["cnpj"],
            placeholder="14 dígitos"
        )

    with col2:
        cuf_manual = st.text_input(
            "cUF / cOrgao",
            value=dados_xml["cuf"],
            placeholder="Exemplo: 35"
        )

    justificativa = st.text_area(
        "Justificativa do cancelamento",
        value="Informacoes erradas",
        height=100
    )

    if st.button("Gerar XML de Cancelamento", use_container_width=True):
        dados = {
            "chave": limpar_numeros(chave_manual),
            "protocolo": limpar_numeros(protocolo_manual),
            "cnpj": limpar_numeros(cnpj_manual),
            "cuf": limpar_numeros(cuf_manual),
            "cmun": "",
        }

        # Se a chave foi informada, usa ela para completar cUF e CNPJ quando possível.
        if validar_chave_mdfe(dados["chave"]):
            if not dados["cuf"]:
                dados["cuf"] = dados["chave"][:2]

            if not dados["cnpj"]:
                dados["cnpj"] = dados["chave"][6:20]

        if not justificativa.strip():
            st.error("Informe a justificativa do cancelamento.")
            return

        try:
            validar_dados_cancelamento(dados)
        except Exception as e:
            st.error(str(e))
            return

        instante = gerar_instante_evento()

        xml_final = montar_xml_cancelamento(
            chave=dados["chave"],
            cnpj=dados["cnpj"],
            cuf=dados["cuf"],
            protocolo=dados["protocolo"],
            justificativa=justificativa,
            instante=instante
        )

        nome_arquivo = gerar_nome_arquivo(dados["chave"], "can")

        mostrar_resultado(
            dados=dados,
            nome_arquivo=nome_arquivo,
            xml_final=xml_final,
            mostrar_cmun=False
        )


MOTIVOS_INSUCESSO = {
    "1": "Recebedor não encontrado",
    "2": "Recusa",
    "3": "Endereço inexistente",
    "4": "Outros",
}


def extrair_dados_cte(xml_bytes: bytes) -> dict:
    """Lê CTe ou cteProc, com ou sem namespace, sem confundir emitente e destinatário."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"XML inválido: {exc}") from exc
    infos = [e for e in root.iter() if nome_tag(e) == "infCte"]
    if len(infos) != 1:
        raise ValueError("Envie o XML de um único CT-e (CTe ou cteProc).")
    inf = infos[0]
    match = re.fullmatch(r"CTe([0-9]{44})", inf.get("Id", ""))
    protocolos = {
        buscar_primeiro_texto(e, "chCTe")
        for e in root.iter() if nome_tag(e) == "protCTe"
    } - {""}
    chave = match.group(1) if match else next(iter(protocolos), "")
    if not re.fullmatch(r"[0-9]{44}", chave) or chave[20:22] != "57":
        raise ValueError("Não foi encontrada uma chave válida de CT-e modelo 57.")
    if protocolos and protocolos != {chave}:
        raise ValueError("A chave do protocolo difere da chave do CT-e.")
    emit = next((e for e in inf if nome_tag(e) == "emit"), None)
    cnpj = buscar_primeiro_texto(emit, "CNPJ") if emit is not None else ""
    cnpj = cnpj or chave[6:20]
    if not re.fullmatch(r"[0-9]{14}", cnpj) or cnpj != chave[6:20]:
        raise ValueError("O CNPJ do emitente não corresponde à chave do CT-e.")
    return {"chave": chave, "cnpj": cnpj}


def montar_xml_insucesso(
    chave: str,
    cnpj: str,
    motivo: str,
    justificativa: str,
    instante: datetime,
    tentativa: datetime,
) -> str:
    """Gera o pedido conforme o modelo informado, sem assinatura ou envio."""
    if not re.fullmatch(r"[0-9]{44}", chave):
        raise ValueError("Informe uma chave CT-e com 44 dígitos.")
    if chave[20:22] != "57":
        raise ValueError("A chave deve pertencer a um CT-e (modelo 57).")
    if not re.fullmatch(r"[0-9]{14}", cnpj):
        raise ValueError("Informe um CNPJ com 14 dígitos.")
    if motivo not in MOTIVOS_INSUCESSO:
        raise ValueError("Selecione um motivo de 1 a 4.")
    justificativa = justificativa.strip()
    if not 15 <= len(justificativa) <= 256:
        raise ValueError("A justificativa deve ter de 15 a 256 caracteres.")
    if any(
        not (c in "\t\n\r" or 0x20 <= ord(c) <= 0xD7FF
             or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF)
        for c in justificativa
    ):
        raise ValueError("A justificativa contém caracteres inválidos para XML.")
    if instante.utcoffset() is None or tentativa.utcoffset() is None:
        raise ValueError("As datas devem incluir o fuso horário.")
    if tentativa > instante:
        raise ValueError("A tentativa de entrega não pode ser posterior ao evento.")

    # Mantém os valores fixos e a sequência de três dígitos do modelo de CT-e.
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<eventoCTe versao="4.00">
  <infEvento Id="ID110190{chave}001">
    <cOrgao>35</cOrgao>
    <tpAmb>1</tpAmb>
    <CNPJ>{cnpj}</CNPJ>
    <chCTe>{chave}</chCTe>
    <dhEvento>{gerar_dh_evento(instante.astimezone(FUSO_BR))}</dhEvento>
    <tpEvento>110190</tpEvento>
    <nSeqEvento>001</nSeqEvento>
    <detEvento versaoEvento="4.00">
      <evInsucessoEntregaCTe>
        <descEvento>Insucesso na Entrega do CT-e</descEvento>
        <tpMotivo>{motivo}</tpMotivo>
        <xJust>{escape(justificativa)}</xJust>
        <dhTentativaEntrega>{gerar_dh_evento(tentativa.astimezone(FUSO_BR))}</dhTentativaEntrega>
      </evInsucessoEntregaCTe>
    </detEvento>
  </infEvento>
</eventoCTe>'''


def tela_insucesso() -> None:
    st.subheader("Insucesso na Entrega do CT-e")
    st.info(
        "Envie o XML do CT-e, com ou sem protocolo. A chave e o CNPJ do emitente "
        "serão extraídos automaticamente. Complete os dados da tentativa de entrega."
    )
    st.caption("Padrão do modelo: órgão 35 · produção · sequência 001.")
    xml_file = st.file_uploader("Envie o XML do CT-e", type=["xml"], key="ins_xml")
    xml_bytes = xml_file.getvalue() if xml_file is not None else None
    identificador = hashlib.sha256(xml_bytes).hexdigest() if xml_bytes is not None else None
    if st.session_state.get("ins_arquivo") != identificador:
        for key in list(st.session_state):
            if key.startswith("ins_") and key not in {"ins_xml", "ins_arquivo"}:
                del st.session_state[key]
        st.session_state["ins_arquivo"] = identificador
    if xml_bytes is None:
        st.info("Envie o XML do CT-e para continuar.")
        return
    try:
        dados = extrair_dados_cte(xml_bytes)
    except ValueError as exc:
        st.session_state.pop("ins_resultado", None)
        st.error(str(exc))
        return
    chave, cnpj = dados["chave"], dados["cnpj"]
    st.success("Dados extraídos do XML.")
    st.write(f"**Chave do CT-e:** `{chave}`")
    st.write(f"**CNPJ do emitente:** `{cnpj}`")
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
