import requests
import pandas as pd
import random
import time
import os
from fake_useragent import UserAgent
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURAÇÕES GLOBAIS ---
BASE_URL = "https://veiculos.fipe.org.br/api/veiculos"
ANO_MODELO_MIN = 2010
MES_REFERENCIA, ANO_REFERENCIA = 1, 2026

# Configuração de Sessão e Retries (Para evitar quedas de conexão)
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

def get_headers():
    return {
        "Referer": random.choice(["https://veiculos.fipe.org.br/", "http://veiculos.fipe.org.br/"]),
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": UserAgent().random
    }

# --- FUNÇÕES ---

def consultar_tabela_referencia(mes=None, ano=None):
    url = f"{BASE_URL}/ConsultarTabelaDeReferencia"
    response = session.post(url, headers=get_headers())
    
    if response.status_code != 200:
        raise Exception(f"Erro ao buscar referências: {response.status_code}")
    
    lista_referencias = response.json()
    if mes is None or ano is None:
        return lista_referencias[0]

    meses_nomes = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
    }
    
    busca_str = f"{meses_nomes[mes]}/{ano}"
    for ref in lista_referencias:
        if ref['Mes'].strip().lower() == busca_str.lower():
            return ref
    raise ValueError(f"Referência {busca_str} não encontrada.")

def api_post(endpoint, payload):
    """Função genérica para POST com tratamento de erro"""
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = session.post(url, headers=get_headers(), data=payload, timeout=15)
        # Delay estratégico entre requisições para evitar block
        time.sleep(random.uniform(1.0, 1.5))
        # Verifica se o status é 200 (OK)
        if response.status_code != 200:
            print(f"⚠️ Erro HTTP {response.status_code} no endpoint {endpoint}")
            return None
        return response.json()
    except Exception as e:
        print(f"Erro na requisição {endpoint}: {e}")
        return None

def pegar_dados_fipe(mes_ref, ano_ref, ano_min=2010):
    print("🚀 Iniciando extração de dados...")
    
    ref = consultar_tabela_referencia(mes_ref, ano_ref)
    cod_ref = ref['Codigo']
    
    marcas = api_post("ConsultarMarcas", {"codigoTabelaReferencia": cod_ref, "codigoTipoVeiculo": 1})
    
    dados_acumulados = []
    
    if not marcas: return pd.DataFrame()

    for marca in marcas:
        print(f"📦 Processando Marca: {marca['Label']}")
        modelos_resp = api_post("ConsultarModelos", {
            "codigoTabelaReferencia": cod_ref,
            "codigoTipoVeiculo": 1,
            "codigoMarca": marca['Value']
        })
        
        if not modelos_resp: continue
        
        for modelo in modelos_resp['Modelos']:
            
            anos = api_post("ConsultarAnoModelo", {
                "codigoTabelaReferencia": cod_ref,
                "codigoTipoVeiculo": 1,
                "codigoMarca": marca['Value'],
                "codigoModelo": modelo['Value']
            })
            
            if not anos: continue
            
            for ano in anos:
                ano_val = int(ano['Value'].split('-')[0])
                if ano_val >= ano_min:
                    ano_cod, combustivel_cod = ano['Value'].split('-')
                    
                    detalhes = api_post("ConsultarValorComTodosParametros", {
                        "codigoTabelaReferencia": cod_ref,
                        "codigoTipoVeiculo": 1,
                        "codigoMarca": marca['Value'],
                        "codigoModelo": modelo['Value'],
                        "anoModelo": ano_cod,
                        "codigoTipoCombustivel": combustivel_cod,
                        "tipoConsulta": "tradicional"
                    })
                    
                    if detalhes:
                        dados_acumulados.append(detalhes)
                        # Print de progresso rápido
                        print(f"  ✅ {detalhes['Modelo']} {detalhes['AnoModelo']}")

    return pd.DataFrame(dados_acumulados)

# --- EXECUÇÃO ---
try:
    df_final = pegar_dados_fipe(MES_REFERENCIA, ANO_REFERENCIA, ANO_MODELO_MIN)

    if not df_final.empty:
        filename = f"fipe_{MES_REFERENCIA}_{ANO_REFERENCIA}.csv"
        df_final.to_csv(filename, index=False, sep=';', decimal=',', encoding='utf-8-sig')
        print(f"\n✨ Sucesso! Arquivo '{filename}' gerado com {len(df_final)} registros.")
    else:
        print("\n⚠️ Nenhum dado foi coletado.")
except Exception as e:
    print(f"\n❌ Erro crítico: {e}")
