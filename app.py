from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

import streamlit as st


FUSO_BR = timezone(timedelta(hours=-3))
NS = {"mdfe": "http://www.portalfiscal.inf.br/mdfe"}


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


def gerar_id_evento(chave: str) -> str:
    return f"ID110112{chave}01"


def gerar_nome_arquivo(chave: str) -> str:
    return f"env_{chave}enc-ped-evt.xml"


def extrair_dados_do_xml_processado(xml_bytes: bytes) -> dict:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"XML inválido: {e}")

    chave = limpar_numeros(
        root.findtext(".//mdfe:protMDFe/mdfe:infProt/mdfe:chMDFe", default="", namespaces=NS)
    )

    if not chave:
        inf_mdfe = root.find(".//mdfe:infMDFe", NS)
        if inf_mdfe is not None:
            id_attr = inf_mdfe.attrib.get("Id", "")
            chave = limpar_numeros(id_attr.replace("MDFe", ""))

    protocolo = limpar_numeros(
        root.findtext(".//mdfe:protMDFe/mdfe:infProt/mdfe:nProt", default="", namespaces=NS)
    )

    cnpj = limpar_numeros(
        root.findtext(".//mdfe:emit/mdfe:CNPJ", default="", namespaces=NS)
    )

    cuf = limpar_numeros(
        root.findtext(".//mdfe:ide/mdfe:cUF", default="", namespaces=NS)
    )

    cmun = limpar_numeros(
        root.findtext(".//mdfe:emit/mdfe:enderEmit/mdfe:cMun", default="", namespaces=NS)
    )

    if not validar_chave_mdfe(chave):
        raise ValueError("Não foi possível extrair uma chave válida de 44 dígitos do XML processado.")

    if not validar_protocolo(protocolo):
        raise ValueError("Não foi possível extrair um protocolo válido do XML processado.")

    if len(cnpj) != 14:
        raise ValueError("Não foi possível extrair um CNPJ válido do XML processado.")

    if len(cuf) != 2:
        raise ValueError("Não foi possível extrair um cUF válido do XML processado.")

    if len(cmun) != 7:
        raise ValueError("Não foi possível extrair um cMun válido do XML processado.")

    return {
        "chave": chave,
        "protocolo": protocolo,
        "cnpj": cnpj,
        "cuf": cuf,
        "cmun": cmun,
    }


def montar_xml(chave: str, cnpj: str, cuf: str, protocolo: str, cmun: str, instante: datetime) -> str:
    return f"""<eventoMDFe versao="3.00" xmlns="http://www.portalfiscal.inf.br/mdfe">
  <infEvento Id="{gerar_id_evento(chave)}">
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


def main() -> None:
    st.set_page_config(
        page_title="Gerador XML Encerramento MDF-e",
        layout="centered"
    )

    st.title("Gerador de XML de Encerramento de MDF-e")
    st.write("Envie o XML Documento processado (Proc/ProcEvento). O sistema extrai automaticamente chave, protocolo, CNPJ, cUF e cMun.")

    xml_file = st.file_uploader(
        "Documento processado do MDF-e (.xml)",
        type=["xml"]
    )

    if st.button("Gerar XML", use_container_width=True):
        if xml_file is None:
            st.error("Envie o XML Documento processado.")
            return

        try:
            dados = extrair_dados_do_xml_processado(xml_file.read())
        except Exception as e:
            st.error(str(e))
            return

        instante = gerar_instante_evento()

        xml_final = montar_xml(
            chave=dados["chave"],
            cnpj=dados["cnpj"],
            cuf=dados["cuf"],
            protocolo=dados["protocolo"],
            cmun=dados["cmun"],
            instante=instante
        )

        nome_arquivo = gerar_nome_arquivo(dados["chave"])

        st.success("XML gerado com sucesso.")
        st.subheader("Dados extraídos")
        st.write(f"**Chave:** `{dados['chave']}`")
        st.write(f"**Protocolo:** `{dados['protocolo']}`")
        st.write(f"**CNPJ:** `{dados['cnpj']}`")
        st.write(f"**cUF / cOrgao:** `{dados['cuf']}`")
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


if __name__ == "__main__":
    main()