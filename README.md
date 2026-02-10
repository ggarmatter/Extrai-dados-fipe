# Extrai Dados FIPE

Este repositório contém um script em Python para a extração de dados da Tabela FIPE (Fundação Instituto de Pesquisas Econômicas).

O script utiliza a biblioteca `cloudscraper` para realizar as requisições HTTP e `pandas` para a manipulação e salvamento dos dados em formato CSV.

## Funcionalidades

* **Requisições:** Utiliza `cloudscraper` para simular um navegador (Chrome/Windows) e realizar chamadas à API da FIPE.
* **Verificação de Histórico:** Antes de processar um modelo, o script verifica no arquivo de saída se ele já foi baixado. Caso positivo, o modelo é pulado.
* **Salvamento Incremental:** Os dados são gravados no arquivo CSV a cada modelo processado (modo *append*).
* **Formatação:** O arquivo de saída utiliza ponto e vírgula (`;`) como separador e vírgula (`,`) para decimais (encoding `utf-8-sig`).
* **Filtros:** Configurado por padrão para extrair dados de carros (Tipo 1) a partir do ano de 2018.

## Tecnologias

* Python 3
* Cloudscraper
* Pandas
* Requests

## Instalação

1. **Clone o repositório**
   ```bash
   git clone [https://github.com/ggarmatter/Extrai-dados-fipe.git](https://github.com/ggarmatter/Extrai-dados-fipe.git)
   cd Extrai-dados-fipe
   ```

2. **Crie um ambiente virtual (Opcional)**
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

3. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

## Como Usar

Execute o script principal:

```bash
python pegar_fipe.py
```

O script criará uma pasta chamada `download` no diretório raiz e salvará o arquivo no padrão:
`./download/fipe_{MES}_{ANO}.csv`

### Configuração

Para alterar o mês de referência, ano de referência ou o ano mínimo dos veículos, edite os parâmetros da função `main` no final do arquivo `pegar_fipe.py`:

```python
if __name__ == '__main__':
    # Exemplo: Referência mês 1/2024, filtro ano 2015
    main(mes_ref=1, ano_ref=2024, ano_modelo_min=2015)
```

## Estrutura do CSV

O arquivo gerado contém as seguintes colunas:

* `Valor`
* `Marca`
* `Modelo`
* `AnoModelo`
* `Combustivel`
* `CodigoFipe`
* `MesReferencia`
* `Autenticacao`
* `TipoVeiculo`
* `SiglaCombustivel`
* `DataConsulta`
* `DataExtracao`

## Aviso Legal

Este projeto tem fins educacionais. Os dados da Tabela FIPE são propriedade da Fundação Instituto de Pesquisas Econômicas.