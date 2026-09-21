from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


def _layout(title: str, subtitle: str, body: str) -> HTMLResponse:
    html = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · CDM Desmontes</title>
<style>
:root{{color-scheme:dark;background:#0d1219;color:#eef2f7;font-family:Inter,Arial,sans-serif}}
*{{box-sizing:border-box}}body{{margin:0;background:#0d1219;color:#eef2f7}}
main{{width:min(920px,calc(100% - 32px));margin:48px auto 80px}}
a{{color:#8fb3ff}}.brand{{font-size:11px;letter-spacing:.18em;color:#8994a4;font-weight:800}}
h1{{font-size:36px;margin:12px 0 8px}}.sub{{color:#98a2b3;line-height:1.65;margin-bottom:30px}}
article{{background:#151b24;border:1px solid #232c39;border-radius:16px;padding:28px}}
h2{{font-size:18px;margin:28px 0 8px}}h2:first-child{{margin-top:0}}
p,li{{font-size:14px;line-height:1.7;color:#c7cfda}}ul{{padding-left:20px}}
.note{{margin-top:24px;padding:14px;border-radius:10px;background:#202938;color:#aeb9c8;font-size:12px;line-height:1.55}}
footer{{margin-top:22px;font-size:12px;color:#7e8999}}
</style>
</head>
<body><main><div class="brand">CDM DESMONTES</div><h1>{escape(title)}</h1>
<p class="sub">{escape(subtitle)}</p><article>{body}</article>
<footer>Versão publicada em 21/09/2026 · <a href="/">Voltar ao CDM</a></footer></main></body></html>'''
    return HTMLResponse(html)


@router.get("/termos", response_class=HTMLResponse)
def termos():
    body = '''
<h2>1. Objeto</h2>
<p>Estes Termos regulam o uso do CDM Desmontes, plataforma de gestão para desmanches e autopeças, incluindo estoque, vendas, integrações, recursos fiscais, financeiros e administrativos.</p>
<h2>2. Conta e acesso</h2>
<p>O responsável pela conta deve fornecer informações corretas, manter suas credenciais em segurança e controlar os usuários autorizados da empresa. Ações executadas por usuários autenticados podem ser registradas para auditoria e segurança.</p>
<h2>3. Assinatura e cobrança</h2>
<p>Valores, período de teste, eventual implantação, recorrência e condições comerciais aplicáveis são os apresentados no checkout ou no acordo comercial vigente no momento da contratação. Pagamentos podem ser processados por provedores externos.</p>
<h2>4. Integrações externas</h2>
<p>Mercado Livre, Shopee, OLX, serviços fiscais, meios de pagamento e outros provedores possuem regras e disponibilidade próprias. O CDM não controla aprovações, indisponibilidades ou mudanças realizadas por esses terceiros.</p>
<h2>5. Uso adequado</h2>
<p>O usuário deve utilizar o sistema de forma lícita, manter a regularidade do próprio negócio e conferir informações fiscais, comerciais e cadastrais antes de transmissões oficiais.</p>
<h2>6. Dados e disponibilidade</h2>
<p>O CDM adota controles de acesso, isolamento por empresa, registros de auditoria e rotinas de backup. Manutenções e falhas de infraestrutura ou de terceiros podem causar indisponibilidade temporária.</p>
<h2>7. Cancelamento</h2>
<p>A assinatura pode ser cancelada conforme as condições apresentadas no plano contratado. O cancelamento não elimina automaticamente dados cuja retenção seja necessária para segurança, obrigações legais ou preservação de registros.</p>
<h2>8. Alterações</h2>
<p>Estes Termos podem ser atualizados quando houver mudanças relevantes na plataforma, na operação ou em requisitos legais. A versão vigente ficará disponível nesta página.</p>
<div class="note">Este documento descreve as regras operacionais da plataforma e pode ser complementado por contrato comercial específico. Recomenda-se revisão jurídica antes de expansão comercial relevante.</div>
'''
    return _layout("Termos de Uso", "Regras gerais para utilização da plataforma CDM Desmontes.", body)


@router.get("/privacidade", response_class=HTMLResponse)
def privacidade():
    body = '''
<h2>1. Dados tratados</h2>
<p>O CDM pode tratar dados de cadastro de usuários e empresas, produtos, veículos, estoque, vendas, documentos fiscais, integrações, registros técnicos, auditoria e informações necessárias à cobrança e ao suporte.</p>
<h2>2. Finalidades</h2>
<p>Os dados são utilizados para autenticar usuários, prestar as funcionalidades contratadas, manter segurança e auditoria, processar integrações, emitir documentos quando configurado, prestar suporte, prevenir abuso e cumprir obrigações aplicáveis.</p>
<h2>3. Credenciais e integrações</h2>
<p>Tokens e credenciais técnicas necessários às integrações devem ser armazenados com proteção adequada. O CDM procura evitar exposição dessas informações na interface e nos logs.</p>
<h2>4. Compartilhamento com fornecedores</h2>
<p>Quando habilitados, dados estritamente necessários podem ser enviados a provedores de hospedagem, backup, pagamento, marketplaces, emissão fiscal e outros serviços integrados, de acordo com a função solicitada pelo usuário.</p>
<h2>5. Retenção</h2>
<p>Os dados são mantidos pelo tempo necessário à prestação do serviço, segurança, auditoria, recuperação, cumprimento de obrigações legais e exercício regular de direitos. Prazos específicos podem variar conforme a natureza do registro.</p>
<h2>6. Segurança</h2>
<p>São adotadas medidas como autenticação, controle de permissões, isolamento por empresa, comunicação protegida, auditoria e backups. Nenhum sistema conectado à internet elimina completamente todos os riscos.</p>
<h2>7. Direitos do titular</h2>
<p>Solicitações relacionadas a acesso, correção, portabilidade, eliminação quando aplicável ou outras questões de privacidade podem ser encaminhadas pelo canal de suporte disponibilizado pela plataforma, observadas as hipóteses legais de retenção.</p>
<h2>8. Atualizações</h2>
<p>Este Aviso pode ser atualizado para refletir mudanças na plataforma ou no tratamento de dados. A versão vigente ficará disponível nesta página.</p>
<div class="note">Aviso operacional de privacidade. Para operação comercial em escala, recomenda-se revisão jurídica e complementação com os dados formais do responsável pelo serviço.</div>
'''
    return _layout("Política de Privacidade", "Como o CDM Desmontes trata informações utilizadas para prestar e proteger o serviço.", body)
