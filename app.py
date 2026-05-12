from __future__ import annotations

import re
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


def main() -> None:
    st.set_page_config(
        page_title="Gerador XML MDF-e",
        layout="centered"
    )

    st.title("Gerador de XML MDF-e")

    st.write(
        "Ferramenta para gerar XML de eventos MDF-e. "
        "Escolha abaixo se deseja gerar um evento de encerramento ou cancelamento."
    )

    tipo_evento = st.selectbox(
        "Qual evento deseja gerar?",
        [
            "Encerramento",
            "Cancelamento"
        ]
    )

    st.divider()

    if tipo_evento == "Encerramento":
        tela_encerramento()

    if tipo_evento == "Cancelamento":
        tela_cancelamento()


if __name__ == "__main__":
    main()