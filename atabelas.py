import streamlit as st
import pandas as pd
import re
from collections import defaultdict
import io
import os
import platform

# Detectar se está no Streamlit Cloud
IS_STREAMLIT_CLOUD = (
    os.getenv("STREAMLIT_SHARING_MODE") == "true" or 
    "streamlit" in os.getcwd().lower() or
    platform.system() == "Linux"
)

# BASE DE DADOS: Mapeamento Ativo ALM → Indexador
BASE_DADOS_ALM = {
    # CDI
    "RPPS - Carteira 95% do CDI": "CDI",
    "RPPS - Carteira Fundo Crédito Privado - CDI": "CDI",
    "RPPS - Carteira Fundos Renda Fixa - CDI": "CDI",
    "RPPS - FIDC": "CDI",
    
    # IMA-B
    "RPPS - Carteira Fundo Crédito Privado - IMA-B 5": "IMA-B",
    "RPPS - Carteira Fundo Títulos Públicos - IMA-B 5": "IMA-B",
    "RPPS - Carteira Fundo Títulos Públicos - IMA-B": "IMA-B",
    "RPPS - Carteira Fundos Renda Fixa - IMA-B": "IMA-B",
    "RPPS - CARTEIRA IMA GERAL": "IMA-B",
    "RPPS - FUNDO MULTIMERCADO IMA-B": "IMA-B",
    
    # IRF-M
    "RPPS - Carteira Fundos Renda Fixa - IRF-M": "IRF-M",
    
    # IPCA
    "RPPS - FUNDO VÉRTICE 2026": "IPCA",
    "RPPS - FUNDO VÉRTICE 2027": "IPCA",
    "RPPS - FUNDO VÉRTICE 2028": "IPCA",
    "RPPS - FUNDO VÉRTICE 2029": "IPCA",
    "RPPS - FUNDO VÉRTICE 2030": "IPCA",
    "RPPS - FUNDO VÉRTICE 2033": "IPCA",
    "RPPS - FUNDO VÉRTICE 2035": "IPCA",
    "RPPS - Fundos de Investimentos em Participação": "IPCA",
    "RPPS - Fundos Títulos Públicos - IPCA": "IPCA",
    "RPPS - Fundos Títulos Públicos - IPCA (Vértice 2026)": "IPCA",
    
    # IFIX
    "RPPS - Carteira de Fundos Imobiliários": "IFIX",
    
    # IBOVESPA
    "RPPS - Carteira de Fundos de Ações": "IBOVESPA",
    "RPPS - Carteira Fundos Multimercados - Capital Protegido": "IBOVESPA",
    "RPPS - Carteira Fundos Multimercados - Capital Protegido (Ibovespa - Vencimento 27/07/2026)": "IBOVESPA",
    
    # S&P
    "RPPS - Carteira Multimercado - S&P": "S&P",
    
    # MSCI (corrigido de MSI para MSCI)
    "RPPS - Carteira Fundos de Investimento no Exterior": "MSCI",
    
    # ESTRESSADO
    "RPPS - Carteira Fundos Estressados": "ESTRESSADO",
}

def processar_ntnb(df):
    """Processa dados NTN-B equivalente ao código VBA"""
    try:
        # Verificar se o DataFrame tem dados
        if df is None or df.empty:
            st.error("DataFrame vazio ou inválido")
            return None
            
        # Encontrar o saldo total da carteira
        saldo_total_carteira = 0
        for idx in range(len(df)):
            try:
                row = df.iloc[idx]
                if pd.notna(row.iloc[1]) and str(row.iloc[1]).lower().strip() == "total geral":
                    saldo_total_carteira = float(row.iloc[10]) if pd.notna(row.iloc[10]) else 0
                    break
            except:
                continue
        
        if saldo_total_carteira == 0:
            st.error("Não foi possível encontrar o 'Total Geral' na planilha.")
            return None
        
        # Regex para encontrar vencimentos (6 dígitos)
        regex_venc = re.compile(r'\b\d{6}\b')
        
        # Dicionários para armazenar dados consolidados
        dict_valores = defaultdict(float)
        dict_soma_artigo = defaultdict(float)
        dict_indexador = {}
        dict_soma_indexador = defaultdict(float)
        artigo_keys = set()
        
        # Processar linhas com NTN-B
        for idx in range(1, len(df)):
            try:
                row = df.iloc[idx]
                
                # Coluna E (índice 4) - Ativo
                ativo = str(row.iloc[4]) if pd.notna(row.iloc[4]) else ""
                
                if "NTN-B" in ativo:
                    # Extrair vencimento usando regex
                    match = regex_venc.search(ativo)
                    if match:
                        venc_raw = match.group()
                        venc = f"NTN-B 20{venc_raw[-2:]}"
                    else:
                        venc = "N/A"
                    
                    # Coluna B (índice 1) - Artigo
                    artigo = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
                    
                    # Coluna K (índice 10) - Valor
                    valor = float(row.iloc[10]) if pd.notna(row.iloc[10]) else 0
                    
                    # Coluna O (índice 14) - Indexador
                    indexador = "IPCA (NTN-B)"  # Valor fixo para NTN-B""
                    
                    # Chave temporária
                    chave_temp = f"{artigo}|{venc}"
                    
                    # Consolidar valores
                    dict_valores[chave_temp] += valor
                    dict_soma_artigo[artigo] += valor
                    dict_indexador[artigo] = indexador
                    dict_soma_indexador[indexador] += valor
                    artigo_keys.add(artigo)
            except:
                continue
        
        # Criar DataFrame consolidado
        dados_consolidados = []
        
        for artigo in sorted(artigo_keys):
            # Buscar todos os vencimentos para este artigo
            vencimentos_artigo = []
            for chave, valor in dict_valores.items():
                partes = chave.split("|")
                if partes[0] == artigo:
                    vencimentos_artigo.append({
                        'vencimento': partes[1],
                        'valor': valor,
                        'pct_individual': valor / saldo_total_carteira
                    })
            
            # Ordenar por vencimento
            vencimentos_artigo.sort(key=lambda x: x['vencimento'])
            
            # Calcular dados do artigo
            soma_artigo = dict_soma_artigo[artigo]
            indexador_artigo = dict_indexador.get(artigo, "")
            pct_total_indexador = dict_soma_indexador.get(indexador_artigo, 0) / saldo_total_carteira
            
            # Adicionar linhas ao resultado
            for i, venc_data in enumerate(vencimentos_artigo):
                dados_consolidados.append({
                    'Artigo': artigo if i == 0 else "",
                    'Indexador': indexador_artigo if i == 0 else "",
                    'Vencimento': venc_data['vencimento'],
                    'Valor Total': venc_data['valor'],
                    'Soma por Artigo': soma_artigo if i == 0 else "",
                    '% Total por Indexador': pct_total_indexador if i == 0 else "",
                    '% Individual sobre Total': venc_data['pct_individual']
                })
        
        df_consolidado = pd.DataFrame(dados_consolidados)
        return df_consolidado, saldo_total_carteira
    except Exception as e:
        st.error(f"Erro em processar_ntnb: {str(e)}")
        return None
    

def processar_alm_completo(df_alm):
    """Processa arquivo ALM separando NTN-B e outros fundos"""
    try:
        alm_ntnb = defaultdict(lambda: {'valor': 0, 'peso': 0})
        alm_fundos = defaultdict(lambda: defaultdict(lambda: {'valor': 0, 'peso': 0}))
        
        for idx in range(1, len(df_alm)):
            try:
                row = df_alm.iloc[idx]
                
                # Coluna A (índice 0) - Nome do ativo
                ativo = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                
                # Coluna E (índice 4) - Valor sugerido
                valor_sugerido = float(row.iloc[4]) if pd.notna(row.iloc[4]) else 0
                
                # Coluna G (índice 6) - Peso sugerido
                peso_sugerido = float(row.iloc[6]) if pd.notna(row.iloc[6]) else 0
                
                if "NTN-B" in ativo:
                    # Extrair ano do vencimento para NTN-B
                    match = re.search(r'NTN-B\s+(\d{4})', ativo)
                    if match:
                        ano = match.group(1)
                        venc = f"NTN-B {ano}"
                        
                        alm_ntnb[venc]['valor'] += valor_sugerido
                        alm_ntnb[venc]['peso'] += peso_sugerido
                        
                elif ativo and ativo.strip() != "":
                    # Processar outros fundos usando base de dados
                    indexador = BASE_DADOS_ALM.get(ativo, "NÃO_MAPEADO")
                    
                    alm_fundos[indexador][ativo]['valor'] += valor_sugerido
                    alm_fundos[indexador][ativo]['peso'] += peso_sugerido
                    
            except:
                continue
        
        return dict(alm_ntnb), dict(alm_fundos)
        
    except Exception as e:
        st.error(f"Erro em processar_alm_completo: {str(e)}")
        return {}, {}

def consolidar_dados_finais(df_ntnb, alm_data, saldo_total):
    """Consolida dados NTN-B com sugestões ALM - CORRIGIDO"""
    try:
        # Agrupar dados NTN-B por vencimento
        ntnb_por_venc = {}
        
        if df_ntnb is not None and not df_ntnb.empty:
            for idx in range(len(df_ntnb)):
                try:
                    row = df_ntnb.iloc[idx]
                    venc = row['Vencimento']
                    if venc and venc != "":
                        artigo = row['Artigo'] if 'Artigo' in row else ""
                        indexador = row['Indexador'] if 'Indexador' in row else ""
                        valor = row['Valor Total'] if 'Valor Total' in row else 0
                        
                        # Filtro especial para artigo
                        if artigo == "7º I, Alínea a":
                            indexador = "IPCA (NTN-B)"
                            
                        ntnb_por_venc[venc] = {
                            'valor': valor,
                            'artigo': artigo,
                            'indexador': indexador
                        }
                except:
                    continue

        # Criar dados consolidados finais
        dados_finais = []
        total_valor_carteira = 0
        total_pct_carteira = 0
        total_alm_sugestao = 0
        total_alm_pct = 0
        total_diferenca = 0

        # Obter todos os vencimentos únicos
        todos_vencimentos = set(ntnb_por_venc.keys()) | set(alm_data.keys())

        for vencimento in sorted(todos_vencimentos):
            ntnb_info = ntnb_por_venc.get(vencimento, {'valor': 0, 'artigo': '', 'indexador': ''})
            valor_carteira = ntnb_info['valor']
            artigo = ntnb_info['artigo']
            indexador = ntnb_info['indexador']
            
            # CORREÇÃO: Calcular porcentagem corretamente
            pct_carteira = (valor_carteira / saldo_total) if saldo_total > 0 else 0

            alm_info = alm_data.get(vencimento, {'valor': 0, 'peso': 0})
            alm_valor = alm_info['valor']
            # CORREÇÃO: ALM peso já está em formato decimal (dividir por 100)
            alm_peso = (alm_info['peso'] / 100) if alm_info['peso'] > 0 else 0

            diferenca = alm_valor - valor_carteira
            diferenca_pct = alm_peso - pct_carteira if valor_carteira != 0 else (0 if alm_valor == 0 else float('inf'))

            dados_finais.append({
                'Artigo': artigo,
                'Vencimento': vencimento,
                'Indexador': indexador,
                'Valor': valor_carteira,
                '% Carteira': pct_carteira,  # Decimal (0.05 = 5%)
                'ALM Sugestão R$': alm_valor,
                'ALM Sugestão %': alm_peso,  # Decimal (0.05 = 5%)
                'Diferença (R$)': diferenca,
                'Diferença %': diferenca_pct  # Decimal
            })

            # Somar totais
            total_valor_carteira += valor_carteira
            total_pct_carteira += pct_carteira
            total_alm_sugestao += alm_valor
            total_alm_pct += alm_peso
            total_diferenca += diferenca

        # Calcular diferença % total
        total_diferenca_pct = total_alm_pct - total_pct_carteira  if total_valor_carteira != 0 else 0

        # Adicionar linha de totais
        dados_finais.append({
            'Artigo': 'TOTAL',
            'Vencimento': '',
            'Indexador': '',
            'Valor': total_valor_carteira,
            '% Carteira': total_pct_carteira,
            'ALM Sugestão R$': total_alm_sugestao,
            'ALM Sugestão %': total_alm_pct,
            'Diferença (R$)': total_diferenca,
            'Diferença %': total_diferenca_pct
        })

        # Ordem das colunas
        colunas_ordem = ['Artigo', 'Vencimento', 'Indexador', 'Valor', '% Carteira', 
                        'ALM Sugestão R$', 'ALM Sugestão %', 'Diferença (R$)', 'Diferença %']
        df_final = pd.DataFrame(dados_finais)[colunas_ordem]
        
        return df_final
    except Exception as e:
        st.error(f"Erro em consolidar_dados_finais: {str(e)}")
        return pd.DataFrame()

def processar_fundos_por_indexador_v2(df_posicoes, alm_fundos, saldo_total):
    """Processa fundos com diferenças centralizadas - CORRIGIDO"""
    try:
        # Mapeamento de indexadores (mantido igual)
        mapeamento = {
            'CDI': 'CDI',
            'IMA-B': 'IMA-B',
            'IMA-B TOTAL': 'IMA-B',
            'IMA-B 5': 'IMA-B',
            'IMAB': 'IMA-B',
            'IRF-M': 'IRF-M',
            'IRFM': 'IRF-M',
            'IPCA': 'IPCA',
            'IPCA + 5,00%': 'IPCA',
            'IPCA + 6,00%': 'IPCA',
            'IPCA + 8,00%': 'IPCA',
            'IFIX': 'IFIX',
            'IBOVESPA': 'IBOVESPA',
            'IBOV': 'IBOVESPA',
            "SMALL": 'IBOVESPA',
            'IDIV': 'IBOVESPA',
            'ICON': 'IBOVESPA',
            'S&P': 'S&P',
            'S&P 500': 'S&P',
            'S&P 500 (MOEDA ORIGINAL)': 'S&P',
            'ACWI': 'MSCI',
            'GLOBAL BDRX': 'MSCI',
            'MSCI': 'MSCI',
            'ESTRESSADO': 'ESTRESSADO',
            'IPCA + 7,00%': 'IPCA',
            'IRF-M 1':'IRF-M',
            'IRF-M 1+': 'IRF-M',
            'IGCT': 'IBOVESPA',
            'GLOBAL': 'MSCI',
            'RUSSELL': 'MSCI',
            "SELIC": 'CDI',
            'IMA-S':'CDI',
            'IMAT':'IBOVESPA',
            'IBRX': 'IBOVESPA',
            'IBRX 50': 'IBOVESPA',
        }
        
        def padronizar_indexador(indexador_original, artigo=""):
            # Função mantida igual
            indexador_upper = str(indexador_original).upper().strip() if indexador_original is not None else ""
            artigo_upper = str(artigo).upper().strip() if artigo is not None else ""
            
            # NOVA LÓGICA: Se contém IDIV, mapear para IBOVESPA
            if "IDIV" in indexador_upper:
                return 'IBOVESPA'
            
            if indexador_upper == 'CDI':
                return 'CDI'
            
            artigos_permitidos_msci = ['ARTIGO 9º II', 'ARTIGO 8º I', 'ARTIGO 9º III']
            
            if indexador_upper in ['ACWI', 'GLOBAL BDRX', 'MSCI']:
                artigo_permite_msci = False
                for artigo_permitido in artigos_permitidos_msci:
                    if artigo_permitido in artigo_upper:
                        artigo_permite_msci = True
                        break
                
                if artigo_permite_msci:
                    return 'MSCI'
                else:
                    return indexador_original
            
            if indexador_upper in mapeamento and mapeamento[indexador_upper] == 'MSCI':
                artigo_permite_msci = False
                for artigo_permitido in artigos_permitidos_msci:
                    if artigo_permitido in artigo_upper:
                        artigo_permite_msci = True
                        break
                
                if not artigo_permite_msci:
                    return indexador_original
            
            return mapeamento.get(indexador_upper, indexador_original)
        
        # 1. PROCESSAR POSIÇÕES REAIS DA CARTEIRA (mantido igual)
        fundos_por_indexador = defaultdict(lambda: defaultdict(lambda: {
            'artigo': '',
            'valor_carteira': 0
        }))
        
        for idx in range(1, len(df_posicoes)):
            try:
                row = df_posicoes.iloc[idx]
                
                ativo = str(row.iloc[4]) if pd.notna(row.iloc[4]) else ""
                
                if not ativo or "NTN-B" in ativo or ativo.lower() in ['', 'nan', 'total geral']:
                    continue
                    
                artigo = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
                valor = float(row.iloc[10]) if pd.notna(row.iloc[10]) else 0
                indexador_raw = str(row.iloc[14]) if pd.notna(row.iloc[14]) else ""
                
                indexador = padronizar_indexador(indexador_raw, artigo)
                
                fundos_por_indexador[indexador][ativo]['artigo'] = artigo
                fundos_por_indexador[indexador][ativo]['valor_carteira'] += valor
                
            except:
                continue
        
        # 2. CONSOLIDAR VALORES ALM POR INDEXADOR
        valores_alm_por_indexador = defaultdict(lambda: {'valor_total': 0, 'peso_total': 0})
        
        for indexador_alm, ativos_alm in alm_fundos.items():
            for ativo_alm, dados_alm in ativos_alm.items():
                valores_alm_por_indexador[indexador_alm]['valor_total'] += dados_alm['valor']
                valores_alm_por_indexador[indexador_alm]['peso_total'] += dados_alm['peso']
        
        # 3. GERAR DADOS FINAIS - DIFERENÇAS CENTRALIZADAS
        dados_por_indexador = {}
        
        for indexador, fundos in fundos_por_indexador.items():
            dados_indexador = []
            
            # Valores ALM consolidados para este indexador
            alm_consolidado = valores_alm_por_indexador.get(indexador, {'valor_total': 0, 'peso_total': 0})
            valor_alm_total = alm_consolidado['valor_total']
            peso_alm_total = alm_consolidado['peso_total']
            
            # CALCULAR TOTAIS DA CARTEIRA PARA ESTE INDEXADOR
            total_carteira_indexador = sum(info['valor_carteira'] for info in fundos.values())
            # CORREÇÃO: Calcular porcentagem corretamente
            total_pct_carteira_indexador = (total_carteira_indexador / saldo_total) if saldo_total > 0 else 0
            
            # CALCULAR DIFERENÇAS TOTAIS (centralizadas)
            diferenca_total_rs = valor_alm_total - total_carteira_indexador
            # CORREÇÃO: Converter peso ALM para decimal e calcular diferença
            alm_peso_decimal = (peso_alm_total / 100) if peso_alm_total > 0 else 0
            diferenca_total_pct = alm_peso_decimal - total_pct_carteira_indexador
            
            # Primeira linha recebe valores centralizados
            primeira_linha = True
            
            for fundo, info in fundos.items():
                valor_carteira = info['valor_carteira']
                # CORREÇÃO: Calcular porcentagem corretamente
                pct_carteira = (valor_carteira / saldo_total) if saldo_total > 0 else 0
                
                # VALORES CENTRALIZADOS: apenas na primeira linha
                if primeira_linha and (valor_alm_total > 0 or peso_alm_total > 0):
                    alm_valor = valor_alm_total
                    alm_peso = alm_peso_decimal  # Já convertido para decimal
                    diferenca_rs = diferenca_total_rs
                    diferenca_pct = diferenca_total_pct
                    primeira_linha = False
                else:
                    alm_valor = 0
                    alm_peso = 0
                    diferenca_rs = 0
                    diferenca_pct = 0
                
                dados_indexador.append({
                    'Artigo': info['artigo'],
                    'Vencimentos': fundo,
                    'Indexador': indexador,
                    'Valor': valor_carteira,
                    '% Carteira': pct_carteira,  # Decimal (0.05 = 5%)
                    'ALM Sugestão R$': alm_valor,
                    'ALM Sugestão %': alm_peso,  # Decimal (0.05 = 5%)
                    'Diferença (R$)': diferenca_rs,
                    'Diferença %': diferenca_pct  # Decimal
                })
            
            # TOTAIS (usando valores pré-calculados)
            if dados_indexador:
                dados_indexador.append({
                    'Artigo': 'TOTAL',
                    'Vencimentos': '',
                    'Indexador': '',
                    'Valor': total_carteira_indexador,
                    '% Carteira': total_pct_carteira_indexador,  # Decimal
                    'ALM Sugestão R$': valor_alm_total,
                    'ALM Sugestão %': alm_peso_decimal,  # Decimal
                    'Diferença (R$)': diferenca_total_rs,
                    'Diferença %': diferenca_total_pct  # Decimal
                })
                
                colunas_ordem = ['Artigo', 'Vencimentos', 'Indexador', 'Valor', '% Carteira', 
                               'ALM Sugestão R$', 'ALM Sugestão %', 'Diferença (R$)', 'Diferença %']
                dados_por_indexador[indexador] = pd.DataFrame(dados_indexador)[colunas_ordem]
        
        return dados_por_indexador
        
    except Exception as e:
        st.error(f"Erro em processar_fundos_por_indexador_v2: {str(e)}")
        return {}

def _criar_arquivo_excel_base(caminho, df_ntnb, dados_fundos_por_indexador):
    """Função auxiliar para criar arquivo base sem autofit"""
    with pd.ExcelWriter(caminho, engine='openpyxl') as writer:
        from openpyxl.styles import Font, PatternFill, Alignment
        
        fill_azul = PatternFill(start_color="002060", end_color="002060", fill_type="solid")
        font_branca = Font(color="FFFFFF", bold=True)
        
        def formatar_sem_largura(worksheet, df):
            if df is None or df.empty:
                return
                
            # Formatação do cabeçalho
            for col in range(1, len(df.columns) + 1):
                cell = worksheet.cell(row=1, column=col)
                cell.fill = fill_azul
                cell.font = font_branca
                cell.alignment = Alignment(horizontal='center', vertical='center')

            # Formatação da linha de totais
            ultima_linha = len(df) + 1
            for col in range(1, len(df.columns) + 1):
                cell = worksheet.cell(row=ultima_linha, column=col)
                if worksheet.cell(row=ultima_linha, column=1).value == 'TOTAL':
                    cell.fill = fill_azul
                    cell.font = font_branca
                    cell.alignment = Alignment(horizontal='center', vertical='center')

            # Formatação de colunas específicas
            for row in range(2, len(df) + 2):
                for col_idx, col_name in enumerate(df.columns, 1):
                    cell = worksheet.cell(row=row, column=col_idx)
                    if col_name in ['Valor', 'ALM Sugestão R$', 'Diferença (R$)']:
                        cell.number_format = ' #,##0.00'
                    elif col_name in ['% Carteira', 'ALM Sugestão %', 'Diferença %']:
                        cell.number_format = '0.00'
        
        # Aba NTN-B
        if df_ntnb is not None and not df_ntnb.empty:
            df_ntnb.to_excel(writer, sheet_name='NTN-B', index=False)
            formatar_sem_largura(writer.sheets['NTN-B'], df_ntnb)
        
        # Abas dos fundos (atualizada com MSCI e ESTRESSADO)
        indexadores_ordem = ['CDI', 'IMA-B', 'IRF-M', 'IPCA', 'IFIX', 'IBOVESPA', 'S&P', 'MSCI', 'ESTRESSADO']
        for indexador in indexadores_ordem:
            if indexador in dados_fundos_por_indexador:
                df_indexador = dados_fundos_por_indexador[indexador]
                if not df_indexador.empty:
                    df_indexador.to_excel(writer, sheet_name=indexador, index=False)
                    formatar_sem_largura(writer.sheets[indexador], df_indexador)

def formatar_excel_tabelas_alm(df_ntnb, dados_fundos_por_indexador, usar_autofit=True):
    """Cria arquivo Excel com opção de usar xlwings autofit ou openpyxl manual"""
    output = io.BytesIO()
    
    # Tentar usar xlwings se solicitado
    if usar_autofit and not IS_STREAMLIT_CLOUD:
        try:
            if IS_STREAMLIT_CLOUD:
                raise ImportError("xlwings desabilitado no Streamlit Cloud")
            import xlwings as xw
            import tempfile
            import os
            
            # Criar arquivo temporário
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
                temp_path = temp_file.name
            
            # Criar arquivo com openpyxl primeiro
            _criar_arquivo_excel_base(temp_path, df_ntnb, dados_fundos_por_indexador)
            
            # Aplicar autofit com xlwings
            app = xw.App(visible=False, add_book=False)
            try:
                wb = app.books.open(temp_path)
                
                # AutoFit em todas as planilhas
                for sheet in wb.sheets:
                    sheet.autofit('columns')
                
                wb.save()
                wb.close()
                
                # Ler arquivo final
                with open(temp_path, 'rb') as f:
                    output.write(f.read())
                
                
                
            finally:
                app.quit()
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
            output.seek(0)
            return output
            
        except Exception as e:
            st.warning(F"⚠️ xlwings não disponível ({str(e)}). Usando ajuste manual...")
            # Continuar com método manual
    
    # Método manual (original) como fallback
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        from openpyxl.styles import Font, PatternFill, Alignment
        
        fill_azul = PatternFill(start_color="002060", end_color="002060", fill_type="solid")
        font_branca = Font(color="FFFFFF", bold=True)
        
        def formatar_planilha(worksheet, df):
            """Função auxiliar para formatar uma planilha"""
            if df is None or df.empty:
                return
                
            # Formatação do cabeçalho
            for col in range(1, len(df.columns) + 1):
                cell = worksheet.cell(row=1, column=col)
                cell.fill = fill_azul
                cell.font = font_branca
                cell.alignment = Alignment(horizontal='center', vertical='center')

            # Formatação da linha de totais
            ultima_linha = len(df) + 1
            for col in range(1, len(df.columns) + 1):
                cell = worksheet.cell(row=ultima_linha, column=col)
                if worksheet.cell(row=ultima_linha, column=1).value == 'TOTAL':
                    cell.fill = fill_azul
                    cell.font = font_branca
                    cell.alignment = Alignment(horizontal='center', vertical='center')

            # Formatação de colunas específicas
            for row in range(2, len(df) + 2):
                for col_idx, col_name in enumerate(df.columns, 1):
                    cell = worksheet.cell(row=row, column=col_idx)
                    if col_name in ['Valor', 'ALM Sugestão R$', 'Diferença (R$)']:
                        cell.number_format = '#,##0.00'
                    elif col_name in ['% Carteira', 'ALM Sugestão %', 'Diferença %']:
                        cell.number_format = '0.00'

            # Ajustar largura das colunas (método manual)
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max(max_length + 2, 10), 50)  # Min 10, Max 50
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Aba NTN-B
        if df_ntnb is not None and not df_ntnb.empty:
            df_ntnb.to_excel(writer, sheet_name='NTN-B', index=False)
            formatar_planilha(writer.sheets['NTN-B'], df_ntnb)
        
        # Abas dos fundos por indexador (atualizada)
        indexadores_ordem = ['CDI', 'IMA-B', 'IRF-M', 'IPCA', 'IFIX', 'IBOVESPA', 'S&P', 'MSCI', 'ESTRESSADO']
        
        for indexador in indexadores_ordem:
            if indexador in dados_fundos_por_indexador:
                df_indexador = dados_fundos_por_indexador[indexador]
                if not df_indexador.empty:
                    df_indexador.to_excel(writer, sheet_name=indexador, index=False)
                    formatar_planilha(writer.sheets[indexador], df_indexador)
    
    output.seek(0)
    return output

def ler_arquivo_excel(uploaded_file):
    """Função com múltiplas engines para máxima compatibilidade"""
    try:
        uploaded_file.seek(0)
        st.info(f"🔄 Processando: {uploaded_file.name}")
        
        # MÉTODO 1: Tentar com calamine (engine mais robusta)
        try:
            df = pd.read_excel(
                uploaded_file, 
                header=None, 
                engine='calamine'
            )
            st.success(f"✅ Sucesso com calamine: {len(df)} linhas")
            return df
        except:
            uploaded_file.seek(0)
        
        # MÉTODO 2: Tentar com xlrd
        try:
            df = pd.read_excel(
                uploaded_file, 
                header=None, 
                engine='xlrd'
            )
            st.success(f"✅ Sucesso com xlrd: {len(df)} linhas")
            return df
        except:
            uploaded_file.seek(0)
        
        # MÉTODO 3: Tentar salvar como bytes e recarregar
        try:
            import io
            
            # Ler como bytes
            file_bytes = uploaded_file.read()
            bytes_io = io.BytesIO(file_bytes)
            
            # Tentar pandas sem especificar engine
            df = pd.read_excel(bytes_io, header=None)
            st.success(f"✅ Sucesso com bytes: {len(df)} linhas")
            return df
        except:
            pass
        
        # MÉTODO 4: Conversão via CSV (último recurso)
        try:
            uploaded_file.seek(0)
            
            # Tentar converter para CSV primeiro
            temp_df = pd.read_excel(uploaded_file, header=None, engine=None)
            
            # Se chegou aqui, funcionou
            st.success(f"✅ Sucesso engine padrão: {len(temp_df)} linhas")
            return temp_df
            
        except Exception as e:
            st.error(f"❌ Todos os métodos falharam")
            st.error("🔧 **Solução:** Converter o arquivo para CSV")
            st.info("1. Abra o arquivo no Excel")
            st.info("2. Salvar Como → CSV (UTF-8)")
            st.info("3. Use o arquivo CSV gerado")
            return None
        
    except Exception as e:
        st.error(f"❌ Erro geral: {str(e)}")
        return None
# FUNÇÃO PARA GERENCIAR A BASE DE DADOS
def exibir_gerenciador_base_dados():
    """Interface para visualizar e gerenciar a base de dados ALM"""
    st.markdown("---")
    st.subheader("🗄️ Gerenciador da Base de Dados ALM")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**📋 Base de Dados Atual:**")
        df_base = pd.DataFrame([
            {'Ativo ALM': ativo, 'Indexador': indexador} 
            for ativo, indexador in BASE_DADOS_ALM.items()
        ])
        st.dataframe(df_base, use_container_width=True)
    
    with col2:
        st.markdown("**📊 Resumo por Indexador:**")
        resumo = df_base['Indexador'].value_counts()
        for indexador, count in resumo.items():
            st.write(f"• **{indexador}**: {count} ativos")
    
    # Opção para adicionar novos mapeamentos
    with st.expander("➕ Adicionar Novo Mapeamento"):
        col_a, col_b, col_c = st.columns([2, 2, 1])
        
        with col_a:
            novo_ativo = st.text_input("Nome do Ativo ALM:", key="novo_ativo")
        
        with col_b:
            novo_indexador = st.selectbox(
                "Indexador:",
                ['CDI', 'IMA-B', 'IRF-M', 'IPCA', 'IFIX', 'IBOVESPA', 'S&P', 'MSCI', 'ESTRESSADO'],
                key="novo_indexador"
            )
        
        with col_c:
            if st.button("Adicionar", key="btn_adicionar"):
                if novo_ativo and novo_ativo not in BASE_DADOS_ALM:
                    BASE_DADOS_ALM[novo_ativo] = novo_indexador
                    st.success(f"✅ Adicionado: {novo_ativo} → {novo_indexador}")
                    st.rerun()
                elif novo_ativo in BASE_DADOS_ALM:
                    st.error("❌ Ativo já existe na base!")
                else:
                    st.error("❌ Digite o nome do ativo!")

# INTERFACE PRINCIPAL
st.set_page_config(page_title="Consolidador de Carteira", layout="wide")

st.title("📊 Consolidador com Sugestões ALM")
st.markdown("---")

# Adicionar gerenciador da base de dados
if st.checkbox("🗄️ Exibir Gerenciador da Base de Dados"):
    exibir_gerenciador_base_dados()

# Upload dos arquivos em colunas
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Arquivo de Posições (Carteira)")
    uploaded_file_posicoes = st.file_uploader(
        "Selecione o arquivo Excel com as posições",
        type=["xlsx", "xls"],
        key="posi",
        help="Arquivo com dados da carteira atual"
    )

with col2:
    st.subheader("💡 Arquivo de Sugestões ALM")
    uploaded_file_alm = st.file_uploader(
        "Selecione o arquivo Excel com sugestões ALM",
        type=["xlsx", "xls"],
        key="alm",
        help="Arquivo com valores e pesos sugeridos"
    )

# Processar quando ambos os arquivos estiverem carregados
if uploaded_file_posicoes is not None and uploaded_file_alm is not None:
    try:
        # Ler arquivos
        with st.spinner("📊 Lendo arquivo de posições..."):
            df_posicoes = ler_arquivo_excel(uploaded_file_posicoes)
            
        with st.spinner("💡 Lendo arquivo ALM..."):
            df_alm = ler_arquivo_excel(uploaded_file_alm)
        
        if df_posicoes is None or df_alm is None:
            st.error("Erro ao ler os arquivos. Verifique se estão no formato correto.")
            st.stop()
        
        st.success("✅ Arquivos carregados com sucesso!")
        # DEBUG TEMPORÁRIO - REMOVER DEPOIS
if df_alm is not None:
    st.write("🔍 **DEBUG - Primeiras 10 linhas do arquivo ALM:**")
    st.dataframe(df_alm.head(10))
    
    st.write("🔍 **DEBUG - Estrutura do arquivo ALM:**")
    st.write(f"Linhas: {len(df_alm)}, Colunas: {len(df_alm.columns)}")
    
    # Verificar colunas específicas que o código espera
    if len(df_alm.columns) > 6:
        st.write("🔍 **DEBUG - Amostras das colunas importantes:**")
        st.write("Coluna A (Ativo):", df_alm.iloc[1:6, 0].tolist())
        st.write("Coluna E (Valor):", df_alm.iloc[1:6, 4].tolist()) 
        st.write("Coluna G (Peso):", df_alm.iloc[1:6, 6].tolist())
    else:
        st.error("❌ Arquivo ALM tem poucas colunas!")
        
        # Processar NTN-B
        with st.spinner("🔄 Processando dados NTN-B..."):
            resultado_ntnb = processar_ntnb(df_posicoes)
            
        if resultado_ntnb is None:
            st.error("Erro ao processar NTN-B")
            st.stop()
            
        df_ntnb_consolidado, saldo_total = resultado_ntnb
        
        # Processar ALM com base de dados
        with st.spinner("🔄 Processando sugestões ALM com base de dados..."):
            alm_ntnb, alm_fundos = processar_alm_completo(df_alm)
            # DEBUG - Resultado do processamento
st.write("🔍 **DEBUG - Resultado processamento ALM:**")
st.write("ALM NTN-B:", dict(alm_ntnb))
st.write("ALM Fundos:", dict(alm_fundos))
        
        # Consolidar dados NTN-B
        with st.spinner("🔄 Consolidando dados NTN-B..."):
            df_final = consolidar_dados_finais(df_ntnb_consolidado, alm_ntnb, saldo_total)
        
        # Processar fundos com nova função
        with st.spinner("🔄 Processando fundos por indexador..."):
            dados_fundos_por_indexador = processar_fundos_por_indexador_v2(df_posicoes, alm_fundos, saldo_total)
        
        # Exibir resultados
        st.markdown("---")
        st.subheader("📋 Consolidação Final - NTN-B vs ALM")
        
        if df_final is not None and not df_final.empty:
            # Formatar para exibição
            df_display = df_final.copy()
            for idx in range(len(df_display)):
                row = df_display.iloc[idx]
                df_display.at[idx, 'Valor'] = f"R$ {row['Valor']:,.2f}"
                df_display.at[idx, '% Carteira'] = f"{row['% Carteira']:.2%}"
                df_display.at[idx, 'ALM Sugestão R$'] = f"R$ {row['ALM Sugestão R$']:,.2f}"
                df_display.at[idx, 'ALM Sugestão %'] = f"{row['ALM Sugestão %']:.2%}"
                df_display.at[idx, 'Diferença (R$)'] = f"R$ {row['Diferença (R$)']:,.2f}"
                df_display.at[idx, 'Diferença %'] = f"{row['Diferença %']:.2%}"
            
            # Função para destacar linha de total
            def highlight_total(row):
                if row['Artigo'] == 'TOTAL':
                    return ['background-color: #002060; color: white; font-weight: bold'] * len(row)
                return [''] * len(row)
            
            st.dataframe(
                df_display.style.apply(highlight_total, axis=1),
                use_container_width=True
            )
        
        # Preview dos fundos
        if dados_fundos_por_indexador:
            st.markdown("---")
            st.subheader("📊 Preview - Fundos por Indexador")
            
            for indexador, df_indexador in dados_fundos_por_indexador.items():
                if not df_indexador.empty:
                    with st.expander(f"🔍 {indexador} ({len(df_indexador)-1} fundos)"):
                        # Formatar para exibição
                        df_display_idx = df_indexador.copy()
                        for idx in range(len(df_display_idx)):
                            row = df_display_idx.iloc[idx]
                            df_display_idx.at[idx, 'Valor'] = f"R$ {row['Valor']:,.2f}"
                            df_display_idx.at[idx, '% Carteira'] = f"{row['% Carteira']:.2%}"
                            df_display_idx.at[idx, 'ALM Sugestão R$'] = f"R$ {row['ALM Sugestão R$']:,.2f}"
                            df_display_idx.at[idx, 'ALM Sugestão %'] = f"{row['ALM Sugestão %']:.2%}"
                            df_display_idx.at[idx, 'Diferença (R$)'] = f"R$ {row['Diferença (R$)']:,.2f}"
                            df_display_idx.at[idx, 'Diferença %'] = f"{row['Diferença %']:.2%}"
                        
                        st.dataframe(
                            df_display_idx.style.apply(highlight_total, axis=1),
                            use_container_width=True
                        )
        
        # FUNÇÃO PARA PROCESSAR EXCEL COM OPENPYXL
        def processar_excel_com_openpyxl(df_final, dados_fundos_por_indexador, usar_autofit=True):
            """
            Gera o Excel e processa diretamente com openpyxl
            """
            import tempfile
            import os
            from openpyxl import load_workbook
            
            # Cria um arquivo temporário
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
                temp_path = tmp_file.name
            
            try:
                # 1. Gera o Excel inicial
                excel_buffer = formatar_excel_tabelas_alm(df_final, dados_fundos_por_indexador, usar_autofit=False)
                
                # 2. Converte BytesIO para bytes se necessário
                if hasattr(excel_buffer, 'getvalue'):
                    excel_data = excel_buffer.getvalue()
                else:
                    excel_data = excel_buffer
                
                # 3. Salva temporariamente
                with open(temp_path, 'wb') as f:
                    f.write(excel_data)
                
                # 4. Processa com openpyxl
                wb_openpyxl = load_workbook(temp_path)
                
                # Processa cada sheet
                for sheet_name in wb_openpyxl.sheetnames:
                    ws = wb_openpyxl[sheet_name]
                    
                    if sheet_name == "NTN-B":
                        # Processa colunas E, G, I na NTN-B (todas as linhas)
                        max_row = ws.max_row
                        for row_num in range(1, max_row + 1):
                            for col in ['E', 'G', 'I']:
                                cell = ws[f"{col}{row_num}"]
                                if cell.value is not None and isinstance(cell.value, (int, float)):
                                    cell.value = cell.value * 100
                    else:
                        # Processa demais sheets
                        # Altera cabeçalho da coluna B se for "Vencimentos"
                        if ws['B1'].value == "Vencimentos":
                            ws['B1'].value = "Fundos"
                        
                        # Multiplica colunas E, G, I por 100 (a partir da linha 2)
                        max_row = ws.max_row
                        for row_num in range(2, max_row + 1):
                            for col in ['E', 'G', 'I']:
                                cell = ws[f"{col}{row_num}"]
                                if cell.value is not None and isinstance(cell.value, (int, float)):
                                    cell.value = cell.value * 100
                    
                    # AUTOFIT: Ajustar largura das colunas automaticamente
                    if usar_autofit:
                        for column in ws.columns:
                            max_length = 0
                            column_letter = column[0].column_letter
                            
                            for cell in column:
                                try:
                                    if cell.value is not None:
                                        cell_length = len(str(cell.value))
                                        if cell_length > max_length:
                                            max_length = cell_length
                                except:
                                    pass
                            
                            # Ajustar largura (mínimo 10, máximo 50)
                            adjusted_width = min(max(max_length + 2, 10), 50)
                            ws.column_dimensions[column_letter].width = adjusted_width
                
                # Salva as alterações
                wb_openpyxl.save(temp_path)
                wb_openpyxl.close()
                
                # 5. Lê o arquivo processado
                with open(temp_path, 'rb') as f:
                    processed_excel_data = f.read()
                
                return processed_excel_data
                
            except Exception as e:
                # Em caso de erro, retorna o Excel original se existir
                st.error(f"Erro no processamento: {str(e)}")
                return excel_data if 'excel_data' in locals() else None
                
            finally:
                # Remove o arquivo temporário
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        # Botão de download com processamento openpyxl
        st.markdown("---")
        
        # Processa e gera o Excel
        with st.spinner("🔄 Processando Excel..."):
            excel_data = processar_excel_com_openpyxl(df_final, dados_fundos_por_indexador, usar_autofit=True)
        
        # Verifica se o processamento foi bem-sucedido
        if excel_data is not None:
            st.download_button(
                label="📥 Download TABELAS ALM ",
                data=excel_data,
                file_name="TABELAS_ALM.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("❌ Erro ao processar o arquivo Excel")
        
    except Exception as e:
        st.error(f"❌ Erro durante o processamento: {str(e)}")
        st.info("Verifique se os arquivos estão no formato correto.")
        
else:
    st.info("👆 Faça upload dos dois arquivos Excel para começar o processamento.")
    
    with st.expander("ℹ️ Informações sobre os arquivos esperados"):
        st.markdown("""
        **Arquivo de Posições:**
        - Deve conter informações sobre a carteira atual
        - Coluna B: Artigo
        - Coluna E: Ativo
        - Coluna K: Valor
        - Coluna O: Indexador
        - Deve ter uma linha com "Total Geral" na coluna B
        
        **Arquivo ALM:**
        - Deve conter sugestões de alocação
        - Coluna A: Nome do ativo
        - Coluna E: Valor sugerido 
        - Coluna G: Peso sugerido (%) 
        
        **⚠️ IMPORTANTE:** O sistema agora usa uma base de dados interna para identificar os indexadores dos ativos ALM.
        Se aparecer avisos sobre "Ativo ALM não encontrado na base de dados", use o gerenciador para adicionar novos mapeamentos.
        """)
