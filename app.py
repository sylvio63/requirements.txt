import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
import io

# Configuração da página do Streamlit
st.set_page_config(page_title="Scanner B3 Pro", layout="wide", page_icon="📈")

# 1. CAPTURA AUTOMÁTICA DOS TICKERS DO IBOVESPA VIA WIKIPÉDIA
@st.cache_data(ttl=86400)  # Atualiza a lista da Wikipédia 1 vez por dia
def capturar_tickers_ibovespa():
    try:
        url = "https://wikipedia.org"
        tabelas = pd.read_html(url)
        df_wiki = tabelas[0]
        coluna_ticker = [col for col in df_wiki.columns if 'Código' in col or 'Ticker' in col]
        if coluna_ticker:
            tickers = df_wiki[coluna_ticker[0]].dropna().unique().tolist()
            return [str(t).strip() for t in tickers]
    except Exception as e:
        st.error(f"Erro ao capturar lista automática. Usando lista de backup. Erro: {e}")
    return ['PETR4', 'VALE3', 'BBAS3', 'ITSA4', 'BBDC4', 'WEGE3', 'ABEV3', 'RENT3', 'CMIG4']

# 2. CAPTURA DE DADOS FUNDAMENTALISTAS + SETOR DA API REAL
@st.cache_data(ttl=3600)  # Mantém cotações em cache por 1 hora
def carregar_dados_mercado(lista_tickers):
    dados_acoes = []
    barra_progresso = st.progress(0, text="Escaneando mercado real...")
    total = len(lista_tickers)
    
    # Dicionário de tradução simples para setores comuns vindos do Yahoo Finance
    traducao_setores = {
        'Financial Services': 'Financeiro',
        'Utilities': 'Utilidade Pública (Energia/Saneamento)',
        'Basic Materials': 'Materiais Básicos (Mineração/Siderurgia)',
        'Energy': 'Energia (Petróleo/Gás)',
        'Consumer Defensive': 'Consumo Não-Cíclico (Alimentos/Bebidas)',
        'Consumer Cyclical': 'Consumo Cíclico (Varejo)',
        'Industrials': 'Bens Industriais',
        'Healthcare': 'Saúde',
        'Technology': 'Tecnologia',
        'Communication Services': 'Telecomunicações'
    }
    
    for idx, ticker in enumerate(lista_tickers):
        try:
            obj = yf.Ticker(f"{ticker}.SA")
            info = obj.info
            
            setor_original = info.get('sector', 'Não Informado')
            setor_traduzido = traducao_setores.get(setor_original, setor_original)
            
            dados_acoes.append({
                'Ticker': ticker,
                'Setor': setor_traduzido,
                'Preço (R$)': info.get('currentPrice', info.get('previousClose', 0)),
                'P/L': info.get('trailingPE', None),
                'P/VP': info.get('priceToBook', None),
                'DY (%)': (info.get('dividendYield', 0) or 0) * 100,
                'ROE (%)': (info.get('returnOnEquity', 0) or 0) * 100
            })
        except Exception:
            continue
        finally:
            barra_progresso.progress((idx + 1) / total, text=f"Analisando {ticker} ({idx+1}/{total})")
            
    barra_progresso.empty()
    return pd.DataFrame(dados_acoes)

# Inicializando componentes
tickers_ibov = capturar_tickers_ibovespa()

st.title("📊 Scanner B3 Pro: Filtros Avançados e Setoriais")
st.markdown(f"Painel conectado ao mercado. Monitorando automaticamente as **{len(tickers_ibov)} empresas** do Ibovespa.")

if st.button("🔄 Forçar Atualização de Dados da Bolsa"):
    st.cache_data.clear()
    st.rerun()

with st.spinner("Buscando dados e categorizando empresas por setor..."):
    df_mercado = carregar_dados_mercado(tickers_ibov)

# 3. FILTROS NA INTERFACE (Organizados em colunas)
st.header("🔍 Painel de Filtros Avançados")
col_s1, col_s2, col_s3, col_s4 = st.columns(4)

with col_s1:
    max_pl = st.slider("Preço / Lucro Máximo (P/L)", 1.0, 40.0, 15.0, step=0.5)
with col_s2:
    max_pvp = st.slider("Preço / Valor Patrimonial Máximo (P/VP)", 0.1, 3.0, 1.5, step=0.1)
with col_s3:
    min_dy = st.slider("Dividend Yield Mínimo (%)", 0.0, 15.0, 4.0, step=0.5)
with col_s4:
    setores_disponiveis = df_mercado['Setor'].dropna().unique().tolist()
    setores_selecionados = st.multiselect(
        "Filtrar por Setor da Economia:",
        options=setores_disponiveis,
        default=setores_disponiveis
    )

# Aplicação ativa de todos os filtros (Múltiplos + Setor)
df_limpo = df_mercado.dropna(subset=['P/L', 'P/VP'])
filtradas = df_limpo[
    (df_limpo['P/L'] <= max_pl) & 
    (df_limpo['P/VP'] <= max_pvp) & 
    (df_limpo['DY (%)'] >= min_dy) &
    (df_limpo['Setor'].isin(setores_selecionados))
].copy()

# 4. EXIBIÇÃO DO RANKING E EXPORTAÇÃO PARA EXCEL
if not filtradas.empty:
    # Algoritmo de Ranking Dinâmico
    filtradas['Rank P/L'] = filtradas['P/L'].rank(ascending=True)
    filtradas['Rank ROE'] = filtradas['ROE (%)'].rank(ascending=False)
    filtradas['Pontuação'] = filtradas['Rank P/L'] + filtradas['Rank ROE']
    filtradas = filtradas.sort_values(by='Pontuação')
    
    df_exibicao = filtradas[['Ticker', 'Setor', 'Preço (R$)', 'P/L', 'P/VP', 'DY (%)', 'ROE (%)']].copy()
    
    st.subheader(f"📋 Oportunidades Encontradas ({len(df_exibicao)} ativos)")
    st.dataframe(
        df_exibicao, 
        use_container_width=True, 
        hide_index=True
    )
    
    # Criando exportação para Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_exibicao.to_excel(writer, index=False, sheet_name='Ações Baratas')
    
    st.download_button(
        label="📥 Exportar Tabela para Excel (.xlsx)",
        data=buffer.getvalue(),
        file_name=f"acoes_baratas_ibovespa_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    # GRÁFICO DE PIZZA (DONUT) SETORIAL
    st.write("")
    st.subheader("📊 Distribuição das Oportunidades por Setor")
    df_setores = df_exibicao['Setor'].value_counts().reset_index()
    df_setores.columns = ['Setor', 'Quantidade']
    
    fig_donut = px.pie(
        df_setores, 
        values='Quantidade', 
        names='Setor', 
        hole=0.4,
        title="Proporção de Empresas Baratas por Setor Econômico"
    )
    fig_donut.update_traces(textinfo='value+percent')
    st.plotly_chart(fig_donut, use_container_width=True)
    
    st.divider()
    
    # 5. ANÁLISE TÉCNICA COM HISTÓRICO CONFIGURÁVEL E CARTÕES DE MÉTRICAS
    st.header("📈 Análise Gráfica Personalizada")
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        ticker_selecionado = st.selectbox(
            "Selecione uma ação para plotar o histórico:", 
            options=filtradas['Ticker'].tolist()
        )
    with col_g2:
        opcoes_periodo = {
            "1 Mês": "1mo",
            "3 Meses": "3mo",
            "6 Meses": "6mo",
            "1 Ano": "1y",
            "5 Anos": "5y"
        }
        periodo_label = st.selectbox("Escolha o Período Histórico:", options=list(opcoes_periodo.keys()), index=3)
        periodo_api = opcoes_periodo[periodo_label]
    
    if ticker_selecionado:
        with st.spinner(f"Carregando dados de {ticker_selecionado}..."):
            acao_hist = yf.Ticker(f"{ticker_selecionado}.SA")
            df_hist = acao_hist.history(period=periodo_api)
            
            if not df_hist.empty:
                df_hist = df_hist.reset_index()
                
                # Extraindo valores máximos, mínimos e último fechamento do período
                preco_maximo = df_hist['High'].max()
                preco_minimo = df_hist['Low'].min()
                ultimo_fechamento = df_hist['Close'].iloc[-1]
                
                # Criando os cartões visuais de dados
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric(
                        label="Último Fechamento", 
                        value=f"R$ {ultimo_fechamento:.2f}"
                    )
                with m2:
                    st.metric(
                        label=f"Preço Mínimo ({periodo_label})", 
                        value=f"R$ {preco_minimo:.2f}",
                        delta=f"{( (ultimo_fechamento / preco_minimo) - 1 ) * 100:.1f}% acima da mínima",
                        delta_color="normal"
                    )
                with m3:
                    st.metric(
                        label=f"Preço Máximo ({periodo_label})", 
                        value=f"R$ {preco_maximo:.2f}",
                        delta=f"{( (ultimo_fechamento / preco_maximo) - 1 ) * 100:.1f}% abaixo da máxima",
                        delta_color="inverse"
                    )
                st.write("")
                
                # Renderização do gráfico de linha
                fig_linha = px.line(
                    df_hist, x='Date', y='Close', 
                    title=f"Evolução de Fechamento de {ticker_selecionado} — Período: {periodo_label}",
                    labels={'Date': 'Data', 'Close': 'Preço de Fechamento (R$)'}
                )
                fig_linha.update_layout(hovermode="x unified")
                st.plotly_chart(fig_linha, use_container_width=True)
            else:
                st.error("Dados históricos indisponíveis no Yahoo Finance para este intervalo.")
else:
    st.warning("Nenhuma ação do Ibovespa preenche os critérios combinados de múltiplos e setores no momento.")
