import requests
import pandas as pd
import random
import time
from fake_useragent import UserAgent


# --- CONFIGURAÇÕES GLOBAIS ---
BASE_URL = "https://veiculos.fipe.org.br/api/veiculos"

# aqui definimos as pausas mínimas e máximas entre cada requisição de preço para não tomar block da api
PAUSA_API_MIN = 1.0 # menos que 1 não rola
PAUSA_API_MAX = 1.0

# aqui definimos o ano do modelo mínimo que queremos. Assim o script roda mais rápido e traz apenas as infos mais relevantes
ANO_MODELO_MIN = 2010

# aqui definimos o mês e ano de referência dos preços que queremos
MES_REFERENCIA, ANO_REFERENCIA = 1, 2026

# --- FUNÇÕES ---

def get_headers():
    return {
        "Referer": random.choice(["https://veiculos.fipe.org.br/", "http://veiculos.fipe.org.br/"]),
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": UserAgent().random
    }

def consultar_tabela_referencia(mes=None, ano=None):
    """
    Busca o código de referência.
    Se mes e ano não forem passados, retorna o mais recente.
    """
    url = f"{BASE_URL}/ConsultarTabelaDeReferencia"
    response = requests.post(url, headers=get_headers())

    if response.status_code != 200:
        print(f"Erro no Servidor: {response.status_code}")
        raise Exception
    lista_referencias = response.json()

    # Retorna o atual se não houver parâmetros
    if mes is None or ano is None:
        return lista_referencias[0]

    meses_nomes = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
    }

    if mes not in meses_nomes:
        raise ValueError("Mês inválido! Use um número entre 1 e 12.")

    busca_str = f"{meses_nomes[mes]}/{ano}"

    for ref in lista_referencias:
        if ref['Mes'].strip() == busca_str:
            return ref

    raise ValueError(f"Não foi encontrada tabela de referência para {busca_str}")


def consultar_marcas(codigo_tabela_ref, tipo_veiculo=1):
    url = f"{BASE_URL}/ConsultarMarcas"
    
    # O servidor da Fipe é rigoroso: os valores devem ser strings
    payload = {
        "codigoTabelaReferencia": codigo_tabela_ref,
        "codigoTipoVeiculo": tipo_veiculo
    }
    response = requests.post(url, headers=get_headers(), data=payload)
    
    if response.status_code != 200:
        print(f"Erro no Servidor: {response.status_code}")
        print(f"Resposta: {response.text}")
        return []
        
    return response.json()



def consultar_modelos(codigo_tabela_ref, codigo_marca, tipo_veiculo=1):
    url = f"{BASE_URL}/ConsultarModelos"
    payload = {
        "codigoTabelaReferencia": codigo_tabela_ref,
        "codigoTipoVeiculo": tipo_veiculo,
        "codigoMarca": codigo_marca
    }
    response = requests.post(url, headers=get_headers(), data=payload)

    if response.status_code != 200:
        print(f"Erro no Servidor: {response.status_code}")
        print(f"Resposta: {response.text}")
        return []
    return response.json()['Modelos']


def consultar_ano_modelo(codigo_tabela_ref, codigo_marca, codigo_modelo, tipo_veiculo=1):
    url = f"{BASE_URL}/ConsultarAnoModelo"
    payload = {
        "codigoTabelaReferencia": codigo_tabela_ref,
        "codigoTipoVeiculo": tipo_veiculo,
        "codigoMarca": codigo_marca,
        "codigoModelo": codigo_modelo
    }
    response = requests.post(url, headers=get_headers(), data=payload)
    if response.status_code != 200:
        print(f"Erro no Servidor: {response.status_code}")
        print(f"Resposta: {response.text}")
        return []
    return response.json()


def consultar_valor(codigo_tabela_ref, codigo_marca, codigo_modelo, ano_modelo, codigo_tipo_combustivel, tipo_veiculo=1):
    url = f"{BASE_URL}/ConsultarValorComTodosParametros"
    payload = {
        "codigoTabelaReferencia": codigo_tabela_ref,
        "codigoTipoVeiculo": tipo_veiculo,
        "codigoMarca": codigo_marca,
        "codigoModelo": codigo_modelo,
        "anoModelo": ano_modelo,
        "codigoTipoCombustivel": codigo_tipo_combustivel,
        "tipoConsulta": "tradicional"
    }
    response = requests.post(url, headers=get_headers(), data=payload)
    if response.status_code != 200:
        print(f"Erro no Servidor: {response.status_code}")
        print(f"Resposta: {response.text}")
        raise Exception
        #return []
    return response.json()

def pausar_api(pausa_api_min=1.0, pausa_api_max=1.0):
    time.sleep(random.uniform(pausa_api_min, pausa_api_max))

def pegar_dados_fipe(mes_referencia, ano_referencia, ano_modelo_min=2010):
    # cria dataframe onde iremos colocar os dados
    df = pd.DataFrame(columns=['Valor', 'Marca', 'Modelo', 'AnoModelo', 'Combustivel', 'CodigoFipe',
        'MesReferencia', 'Autenticacao', 'TipoVeiculo', 'SiglaCombustivel',
        'DataConsulta'])


    # pega código da tabela 
    print("1. Obtendo Tabela de Referência...")
    referencia = consultar_tabela_referencia(mes_referencia, ano_referencia)
    cod_ref = referencia['Codigo']
    cod_ref

    print("\n2. Buscando Marcas...")
    marcas = consultar_marcas(cod_ref, 1)

    for marca in marcas:
        cod_marca = marca['Value']
        print(f"\n3. Buscando Modelos {marca['Label']}...")
        modelos = consultar_modelos(cod_ref, cod_marca)
        pausar_api()
        for modelo in modelos:
            cod_modelo = modelo['Value']
            anos = consultar_ano_modelo(cod_ref, cod_marca, cod_modelo)
            pausar_api()
            anos = [ano for ano in anos if int(ano['Value'].split('-')[0]) > ano_modelo_min] # filtra fora modelos com ano menor que o mínimo
            for ano in anos:
                ano_modelo, tipo_combustivel = ano['Value'].split('-')
                dados_finais = consultar_valor(
                    codigo_tabela_ref=cod_ref,
                    codigo_marca=cod_marca,
                    codigo_modelo=cod_modelo,
                    ano_modelo=ano_modelo,
                    codigo_tipo_combustivel=tipo_combustivel
                )
                df = pd.concat([df, pd.DataFrame([dados_finais])], ignore_index=True)
                pausar_api()
    return df

df = pegar_dados_fipe(MES_REFERENCIA, ANO_REFERENCIA, ANO_MODELO_MIN)
df.to_csv(f'{MES_REFERENCIA}/{ANO_REFERENCIA}.csv', index=False, sep=';', decimal=',')