# Tool reference

50 tools. Generated from source (`inspect.signature` + docstrings); descriptions remain in Portuguese. The internal COM Session parameter is omitted.

Read-only annotations are hints; operator read-only configuration is enforced server-side. Tools prefixed `dxf_` work on files and do not need AutoCAD.

File-writing tools (`dxf_*` writes, `dxf_export`, `plot_to_pdf`, Excel) only accept paths inside `[paths].allowed_dirs` (default: `~/autocad-mcp-workspace`).

## status

_read-only_

```python
status()
```

Diagnóstico do AutoCAD: conectado?, versão, desenho ativo, unidades, nº de entidades, comando ativo.

QUANDO USAR: sempre como PRIMEIRA chamada de uma conversa e ao suspeitar de problema (erro de
conexão, "AutoCAD ocupado"). Se o AutoCAD estiver fechado, retorna ok=false com
error.code="autocad_not_running" (nunca inicia o AutoCAD sozinho).
Parâmetros: nenhum. Exemplo: status() → data.document.units == "mm".

## list_documents

_read-only_

```python
list_documents()
```

Lista os desenhos abertos no AutoCAD (nome, caminho, salvo?, ativo?).

QUANDO USAR: antes de set_active_document, ou quando há mais de um desenho aberto e é preciso
saber em qual as ferramentas vão atuar (sempre no desenho ATIVO).
Exemplo: list_documents() → data.documents[0].name == "SUPORTES-01.dwg".

## set_active_document

_mutating_

```python
set_active_document(name: str)
```

Torna ativo um desenho já aberto, pelo nome (ex.: "SUPORTES-01.dwg") ou caminho completo.

QUANDO USAR: para trocar o desenho-alvo das demais ferramentas. Não abre arquivos novos.
Parâmetros: name (str) — nome ou caminho; comparação sem diferenciar maiúsculas.
Exemplo: set_active_document("SUPORTES-01.dwg").

## save_document

_mutating_

```python
save_document(confirm: bool = False)
```

Salva o desenho ativo POR CIMA do arquivo atual (operação destrutiva: exige confirm=true).

QUANDO USAR: só quando o usuário pediu para gravar. Desenho sem nome (nunca salvo) é recusado —
peça ao usuário para usar SALVARCOMO no AutoCAD. Sem confirm=true retorna ok=false com a prévia.
Parâmetros: confirm (bool). Exemplo: save_document(confirm=true).

## zoom_extents

_mutating_

```python
zoom_extents()
```

Enquadra a vista atual em todos os objetos do desenho (ZOOM Extents).

QUANDO USAR: depois de inserir/desenhar coisas, para o usuário enxergar o resultado.
Não altera o desenho (não entra no histórico de desfazer). Exemplo: zoom_extents().

## list_layers

_read-only_

```python
list_layers(name_filter: str | None = None, limit: int = 0, offset: int = 0)
```

Lista as camadas do desenho: nome, cor (ACI), tipo de linha, ligada, congelada, bloqueada.

QUANDO USAR: para conhecer a estrutura de camadas antes de desenhar, inserir blocos ou checar padrão.
Parâmetros: name_filter (curinga * e ?, ex. "PIPE-*"; opcional), limit (0 = padrão do servidor),
offset (paginação). Exemplo: list_layers(name_filter="SUP*", limit=20).

## create_layer

_mutating_

```python
create_layer(name: str, color: int | str = 7, linetype: str = 'Continuous')
```

Cria uma camada (se já existir, não altera nada e avisa).

QUANDO USAR: antes de desenhar/inserir em uma camada nova. Não é destrutivo.
Parâmetros: name (sem < > / \ " : ; ? * | , = `), color (índice ACI 1-255 ou nome: red/vermelho,
yellow, green, cyan, blue, magenta, white), linetype (deve estar carregado; HIDDEN/CENTER/DASHED/PHANTOM
são carregados de acad.lin automaticamente). Exemplo: create_layer("SUPORTES", color="green", linetype="Continuous").

## check_layer_standard

_read-only_

```python
check_layer_standard(allowed_layers: list[str], ignore_layers: list[str] | None = None, limit: int = 20)
```

Relata entidades do espaço modelo em camadas FORA do padrão informado (não altera nada).

QUANDO USAR: auditoria de desenho antes da entrega ("tem algo fora das camadas do padrão?").
Parâmetros: allowed_layers (nomes ou padrões com * e ?, ex. ["PIPE-*", "SUPORTES"]),
ignore_layers (padrão ["0", "Defpoints"]), limit (máx. de entidades de amostra por camada).
Retorna, por camada fora do padrão: contagem, tipos e handles de amostra; e as camadas do padrão que
não existem no desenho. Não verifica o conteúdo interno de blocos.
Exemplo: check_layer_standard(["PIPE-*", "SUPORTES", "EIXOS"]).

## query_entities

_read-only_

```python
query_entities(type: str | None = None, layer: str | None = None, block_name: str | None = None, bbox: list[float] | None = None, bbox_mode: str = 'window', limit: int = 0, offset: int = 0)
```

Busca entidades por filtros (via SelectionSet + códigos DXF) e devolve resumo paginado.

QUANDO USAR: para "achar" coisas no desenho: todas as linhas da camada X, blocos de um tipo,
textos numa região. Para propriedades completas use get_entity(handle).
Parâmetros: type (nome DXF: LINE, CIRCLE, LWPOLYLINE, TEXT, MTEXT, INSERT...; lista com vírgula;
apelidos: block, polyline), layer (curinga * e ?), block_name (só INSERT; usa o nome efetivo, então
pega blocos dinâmicos), bbox ([xmin, ymin, xmax, ymax] na unidade do desenho; bbox_mode "window" =
inteiramente dentro, "crossing" = toca a janela), limit/offset (paginação; limit 0 = padrão).
Exemplo: query_entities(type="INSERT", block_name="SUP-*", layer="SUPORTES", limit=25).

## get_entity

_read-only_

```python
get_entity(handle: str)
```

Propriedades completas de UMA entidade pelo handle (geometria, cor, tipo de linha, atributos de bloco).

QUANDO USAR: depois de query_entities/read_block_attributes, para inspecionar um item específico.
Parâmetros: handle (string hexadecimal, ex. "2F1A"). Exemplo: get_entity("2F1A").

## draw_line

_mutating_

```python
draw_line(start: list[float], end: list[float], layer: str | None = None)
```

Desenha uma linha no espaço modelo. Desfazível com um Ctrl+Z.

QUANDO USAR: eixos, referências e traçados simples. Parâmetros: start/end ([x, y] ou [x, y, z] na unidade
do desenho), layer (existente; opcional — sem layer usa a camada ativa). Exemplo: draw_line([0, 0], [1500, 0], layer="EIXOS").

## draw_polyline

_mutating_

```python
draw_polyline(points: list[list[float]], closed: bool = False, layer: str | None = None)
```

Desenha uma polilinha por vértices. Todos os Z iguais → polilinha leve 2D (com elevação); Z variados → polilinha 3D.

QUANDO USAR: contornos, traçados de linha de tubulação em planta, perímetros. Parâmetros: points (≥ 2
pontos [x, y] ou [x, y, z]), closed (fecha a figura), layer. Exemplo: draw_polyline([[0,0],[1000,0],[1000,500]], closed=true, layer="EIXOS").

## draw_circle

_mutating_

```python
draw_circle(center: list[float], radius: float, layer: str | None = None)
```

Desenha um círculo. QUANDO USAR: furos, bocais em planta, marcações.

Parâmetros: center ([x, y] ou [x, y, z]), radius (> 0, unidade do desenho), layer. Exemplo: draw_circle([500, 500], 25.4, layer="EIXOS").

## add_text

_mutating_

```python
add_text(text: str, point: list[float], height: float, rotation: float = 0.0, layer: str | None = None)
```

Adiciona texto de linha única. QUANDO USAR: rótulos curtos (TAG, cota, nota).

Parâmetros: text, point (inserção), height (> 0, unidade do desenho), rotation (GRAUS), layer.
Exemplo: add_text("PS-101", [1250, 830], 3.5, layer="TEXTO").

## add_mtext

_mutating_

```python
add_mtext(text: str, point: list[float], width: float, height: float | None = None, layer: str | None = None)
```

Adiciona texto de várias linhas (MText). QUANDO USAR: notas e legendas; use \P para quebra de linha.

Parâmetros: text, point (canto de inserção), width (> 0, largura da caixa), height (altura do texto; opcional), layer.
Exemplo: add_mtext("NOTA 1:\PVer suporte tipo GUIA", [0, -200], 800, height=3.5, layer="TEXTO").

## move_entity

_mutating_

```python
move_entity(handle: str, displacement: list[float])
```

Move uma entidade por um vetor de deslocamento. Desfazível com Ctrl+Z.

QUANDO USAR: reposicionar um item já localizado (query_entities). Parâmetros: handle, displacement ([dx, dy] ou
[dx, dy, dz], unidade do desenho). Exemplo: move_entity("2F1A", [100, 0, 0]).

## copy_entity

_mutating_

```python
copy_entity(handle: str, displacement: list[float], count: int = 1)
```

Copia uma entidade `count` vez(es), cada cópia deslocada mais um `displacement` (arranjo linear).

QUANDO USAR: repetir um item em passo constante (ex. suportes a cada 3000). Máx. 500 cópias.
Parâmetros: handle, displacement ([dx, dy(, dz)]), count (≥ 1). Exemplo: copy_entity("2F1A", [3000, 0, 0], count=5).

## delete_entities

_mutating_

```python
delete_entities(handles: list[str], confirm: bool = False, dry_run: bool = False)
```

Apaga entidades pelos handles. DESTRUTIVO: exige confirm=true. Tudo-ou-nada; um Ctrl+Z desfaz.

QUANDO USAR: só quando o usuário pediu para apagar. FLUXO: dry_run=true lista o que seria apagado;
depois confirm=true. Se algum handle não existir, nada é apagado e o erro lista os ausentes.
Parâmetros: handles (lista de strings hex), confirm, dry_run. Exemplo: delete_entities(["2F1A", "2F1B"], dry_run=true).

## list_block_definitions

_read-only_

```python
list_block_definitions(name_filter: str | None = None, include_xrefs: bool = False, count_instances: bool = False, limit: int = 0, offset: int = 0)
```

Lista as definições de bloco do desenho e as TAGS de atributo de cada uma.

QUANDO USAR: antes de insert_block (para saber nomes e tags válidos) ou de montar planilhas.
Parâmetros: name_filter (curinga * e ?, ex. "SUP-*"), include_xrefs, count_instances (conta as
referências no espaço modelo; mais lento), limit/offset (paginação; as tags só são lidas para a
página pedida). Exemplo: list_block_definitions(name_filter="SUP-*", count_instances=true).

## insert_block

_mutating_

```python
insert_block(name: str, point: list[float], scale: float | list[float] = 1.0, rotation: float = 0.0, layer: str | None = None, attributes: dict[str, typing.Any] | None = None, create_missing_layer: bool = False)
```

Insere UMA referência de bloco (definição já existente) e preenche atributos por TAG.

QUANDO USAR: para colocar um suporte/símbolo em coordenadas conhecidas. Para muitos blocos a partir
de planilha, use import_blocks_from_excel. Desfazível com um Ctrl+Z.
Parâmetros: name (bloco existente; ver list_block_definitions), point ([x, y] ou [x, y, z] na unidade do
desenho), scale (número ou [sx, sy, sz]), rotation (GRAUS, anti-horário), layer (existente, ou crie com
create_missing_layer=true), attributes ({TAG: valor}; tags não existentes geram aviso).
Exemplo: insert_block("SUP-GUIDE", [1250.5, 830, 4200], rotation=90, layer="SUPORTES",
attributes={"TAG": "PS-101", "LINHA": "10-P-1001"}).

## read_block_attributes

_read-only_

```python
read_block_attributes(block_name: str | None = None, layer: str | None = None, limit: int = 0, offset: int = 0)
```

Lê referências de bloco: handle, posição, camada e dicionário TAG → valor de atributos.

QUANDO USAR: para "ler a tabela de suportes do desenho", conferir TAGs, ou antes de atualizar valores.
Parâmetros: block_name (curinga * e ?; vazio = todos os blocos), layer (curinga), limit/offset
(paginação; 0 = padrão do servidor). Exemplo: read_block_attributes(block_name="SUP-*", layer="SUPORTES", limit=100).

## update_block_attributes

_mutating_

```python
update_block_attributes(attributes: dict[str, typing.Any], handle: str | None = None, filter: dict[str, typing.Any] | None = None, dry_run: bool = False, confirm: bool = False)
```

Altera atributos de UM bloco (handle) ou de vários (filter). Sobrescrita exige confirm=true.

QUANDO USAR: corrigir/preencher TAG, TIPO, LINHA etc. FLUXO SEGURO: 1) dry_run=true para ver o antes→depois;
2) repetir com confirm=true. Sem confirm, se houver sobrescrita de valor existente ou mais de 1 bloco
afetado, retorna ok=false com a prévia. Um único Ctrl+Z desfaz tudo.
Parâmetros: attributes ({TAG: novo valor}; '' limpa), handle (string hex) OU filter
({"block_name": "SUP-*", "layer": "SUPORTES", "where": {"LINHA": "10-P-1001"}}), dry_run, confirm.
Exemplo: update_block_attributes({"TIPO": "GUIA"}, filter={"block_name": "SUP-*", "where": {"TIPO": "SHOE"}}, dry_run=true).

## export_blocks_to_excel

_mutating_

```python
export_blocks_to_excel(block_name: str, path: str, layer: str | None = None, sheet_name: str = 'Blocos', confirm: bool = False)
```

Exporta blocos para .xlsx: HANDLE, BLOCO, CAMADA, X, Y, Z, ROTACAO, ESCALA_X/Y/Z + uma coluna por TAG.

QUANDO USAR: gerar a lista/tabela de suportes do desenho, ou obter uma planilha-modelo para depois
editar e reimportar (o arquivo gerado é aceito por import_blocks_from_excel e sync_attributes_from_excel).
Só lê o desenho. Se o arquivo já existir, sobrescrever exige confirm=true (a planilha tem aba INFO com a unidade).
Parâmetros: block_name (curinga * e ?), path (.xlsx, caminho na máquina do usuário), layer (opcional),
sheet_name, confirm. Coordenadas na unidade do desenho.
Exemplo: export_blocks_to_excel("SUP-*", "C:\\proj\\suportes.xlsx", layer="SUPORTES").

## import_blocks_from_excel

_mutating_

```python
import_blocks_from_excel(path: str, sheet: str | None = None, mapping: dict[str, str] | None = None, dry_run: bool = False, confirm: bool = False, block_name: str | None = None, key_tag: str | None = None, layer: str | None = None, update_position: bool = False, create_missing_layer: bool = False, header_row: int = 1)
```

Insere ou atualiza blocos, linha a linha, a partir de uma planilha .xlsx. Um único Ctrl+Z desfaz tudo.

QUANDO USAR: carregar a tabela de suportes (TAG, TIPO, X, Y, Z, LINHA...) no desenho. FLUXO SEGURO:
dry_run=true primeiro (relata inserir/atualizar/erro por linha sem tocar no desenho), depois execute.
Inserções não pedem confirmação; se alguma linha ATUALIZA um bloco existente, exige confirm=true.
Parâmetros: path/sheet/header_row; mapping ({coluna_excel: alvo}, alvo ∈ x,y,z,rotation(graus),scale,
scale_x/y/z,layer,block,handle,ignore ou "attr:TAG"; sem mapping, detecta X/Y/Z/BLOCO/CAMADA/ROTACAO/
ESCALA/HANDLE por nome e trata as demais colunas como atributos de mesmo nome); block_name (bloco padrão
das linhas sem coluna de bloco); key_tag (atributo-chave, ex. "TAG": linha cujo valor já existe no desenho
ATUALIZA o bloco em vez de inserir duplicado); layer (camada padrão); update_position (também move blocos
existentes; padrão false); create_missing_layer. Célula em branco = ignorar (não apaga o atributo).
Erros por linha não abortam o lote. Exemplo:
import_blocks_from_excel("C:\\proj\\suportes.xlsx", block_name="SUP-GUIDE", key_tag="TAG", layer="SUPORTES", dry_run=true).

## sync_attributes_from_excel

_mutating_

```python
sync_attributes_from_excel(path: str, key_tag: str, dry_run: bool = False, confirm: bool = False, sheet: str | None = None, block_name: str | None = None, mapping: dict[str, str] | None = None, header_row: int = 1)
```

Atualiza ATRIBUTOS de blocos já existentes casando pela TAG-chave (não insere nem move nada).

QUANDO USAR: a planilha é a fonte da verdade dos dados (TIPO, LINHA, PESO...) e o desenho deve refletí-la.
FLUXO SEGURO: dry_run=true (mostra antes→depois, não encontrados e ambíguos); depois confirm=true.
Como altera valores em massa, qualquer mudança real exige confirm=true. Um Ctrl+Z desfaz tudo.
Parâmetros: path/sheet/header_row, key_tag (atributo-chave, ex. "TAG"; a planilha precisa de coluna
com esse nome), block_name (restringe o universo; curinga), mapping ({coluna_excel: "TAG_DO_ATRIBUTO"};
sem mapping, cada cabeçalho é o nome da tag). Célula em branco = mantém o valor do desenho.
Exemplo: sync_attributes_from_excel("C:\\proj\\suportes.xlsx", key_tag="TAG", dry_run=true).

## run_lisp

_mutating_

```python
run_lisp(expression: str, confirm: bool = False, wait_seconds: float = 3.0)
```

Executa UMA expressão AutoLISP no AutoCAD via SendCommand. Desligado por padrão (enable_lisp no config.toml).

QUANDO USAR: só quando nenhuma outra ferramenta faz o serviço (ex.: comando específico do Plant 3D).
LIMITAÇÕES REAIS: SendCommand é ASSÍNCRONO e NÃO devolve o resultado do LISP — para ler um valor, faça o LISP
gravá-lo em uma variável de sistema (SETVAR "USERS1" ...) e leia com outra ferramenta/no AutoCAD; não entra
no agrupamento de undo do servidor (o AutoCAD cria o próprio passo). Exige confirm=true; expressão em uma
linha, ≤ 2000 caracteres, parênteses balanceados; funções de arquivo/registro/processo são bloqueadas
(defesa parcial, não é sandbox). Toda execução é registrada no log.
Parâmetros: expression, confirm, wait_seconds (espera até 30 s o AutoCAD ficar ocioso).
Exemplo: run_lisp('(setvar "USERS1" (rtos (getvar "DIMSCALE")))', confirm=true).

## system_capabilities

_read-only_

```python
system_capabilities() -> 'dict[str, Any]'
```

Informa capacidades e restrições sem conectar ou iniciar AutoCAD.

QUANDO USAR: antes de escolher ferramentas; distingue configuração de conexão real.
Parâmetros: nenhum. Exemplo: system_capabilities() informa read_only e limitações Plant 3D.

## snapshot_support_register

_read-only_

```python
snapshot_support_register(block_filter: str | None = None, layer_filter: str | None = None, key_tag: str = 'TAG', type_tag: str = 'TIPO', line_tag: str = 'LINHA')
```

Captura cadastro completo e limitado de suportes, sem alterar entidades ou salvar arquivos.

QUANDO USAR: antes de revisar atributos ou comparar revisões. Exige filtro explícito de bloco/camada.
Parâmetros: block_filter, layer_filter, key_tag/type_tag/line_tag; nomes de atributos configuráveis.
Exemplo: snapshot_support_register(block_filter="SUP-*", type_tag="TYPE", line_tag="LINE").
Retorna data.snapshot para audit_support_register/compare_support_register; recusa exceder o limite.

## audit_support_register

_read-only_

```python
audit_support_register(snapshot: 'SupportSnapshot', allowed_types: 'list[str] | None' = None, expected_tags: 'list[str] | None' = None, limit: 'int' = 200) -> 'dict[str, Any]'
```

Audita TAGs duplicadas, campos vazios e cadastro esperado; totais por linha/tipo sem inferências.

QUANDO USAR: QA de cadastro antes da entrega ou importação Excel; não dimensiona suportes.
Parâmetros: snapshot completo, allowed_types/expected_tags fornecidos pelo projeto, limit=1..500.
Exemplo: audit_support_register(snapshot, allowed_types=["GUIA", "ANCORA"]). Funciona sem AutoCAD.

## compare_support_register

_read-only_

```python
compare_support_register(before: 'SupportSnapshot', after: 'SupportSnapshot', position_tolerance: 'float' = 0.01, allow_document_change: 'bool' = False, limit: 'int' = 200) -> 'dict[str, Any]'
```

Compara revisões por TAG; mostra inseridos/removidos, deslocamentos e atributos alterados.

QUANDO USAR: revisão de cadastros de suportes com unidades/filtros idênticos; funciona sem AutoCAD.
Parâmetros: before/after completos; position_tolerance na unidade do desenho (não tolerância normativa).
Exemplo: compare_support_register(before, after, position_tolerance=1.0). TAGs ambíguas não são casadas.

## dxf_info

_read-only_

```python
dxf_info(path: 'str') -> 'dict[str, Any]'
```

Resume um DXF sem abrir o AutoCAD: versão, unidades, camadas, layouts, blocos, estilos de cota, extensão.

QUANDO USAR: primeiro passo antes de qualquer outra ferramenta dxf_*; confirma unidades e nomes de camada/layout.
Parâmetros: path = caminho do .dxf dentro das pastas permitidas.
Exemplo: dxf_info(path="C:/Users/eu/autocad-mcp-workspace/linha-L12.dxf")

## dxf_query

_read-only_

```python
dxf_query(path: 'str', type: 'str | None' = None, layer: 'str | None' = None, block: 'str | None' = None, layout: 'str | None' = None, limit: 'int' = 50, offset: 'int' = 0) -> 'dict[str, Any]'
```

Lista entidades de um DXF com filtros e paginação (curingas * e ? em layer/block).

QUANDO USAR: inspecionar ou contar entidades de um DXF sem AutoCAD; pagine com offset/limit (máx. 500).
Parâmetros: path; type (LINE, CIRCLE, ARC, LWPOLYLINE, TEXT, MTEXT, INSERT, DIMENSION...); layer; block;
layout (omita para o modelo); limit; offset.
Exemplo: dxf_query(path="a.dxf", type="INSERT", block="SUP-*", layer="SUPORTES", limit=100)

## dxf_get_entity

_read-only_

```python
dxf_get_entity(path: 'str', handle: 'str') -> 'dict[str, Any]'
```

Devolve os detalhes completos de uma entidade do DXF pelo handle.

QUANDO USAR: depois de dxf_query, para ver geometria/atributos de uma entidade específica.
Parâmetros: path; handle (hexadecimal, ex. "2A3").
Exemplo: dxf_get_entity(path="a.dxf", handle="2A3")

## dxf_read_attributes

_read-only_

```python
dxf_read_attributes(path: 'str', block_filter: 'str | None' = None, layer_filter: 'str | None' = None) -> 'dict[str, Any]'
```

Lê os atributos de blocos (ex.: suportes TAG/TIPO/LINHA) direto do DXF, sem AutoCAD.

QUANDO USAR: extrair o cadastro de suportes de um DXF exportado, ou preparar planilha/auditoria offline.
Parâmetros: path; block_filter (ex. "SUP-*"); layer_filter. Recusa mais de 2000 blocos (restrinja o filtro).
Exemplo: dxf_read_attributes(path="linha.dxf", block_filter="SUP-*")

## dxf_sql_query

_read-only_

```python
dxf_sql_query(path: 'str', sql: 'str', limit: 'int' = 200) -> 'dict[str, Any]'
```

Consulta o DXF com SQL SELECT sobre um índice em memória (tabelas entities e attributes).

QUANDO USAR: perguntas agregadas (contagens por camada, blocos sem TAG, comprimento total por camada).
Parâmetros: path; sql (somente SELECT; colunas entities: handle,type,layer,color,block,x,y,z,text,length,radius;
attributes: handle,block,tag,value); limit (máx. 1000).
Exemplo: dxf_sql_query(path="a.dxf", sql="SELECT layer, COUNT(*) n, SUM(length) L FROM entities GROUP BY layer")

## dxf_audit

_read-only_

```python
dxf_audit(path: 'str') -> 'dict[str, Any]'
```

Audita a estrutura do DXF (erros que o AutoCAD acusaria ao abrir) sem alterar o arquivo.

QUANDO USAR: antes de publicar/entregar um DXF gerado ou recebido; relata erros e itens corrigíveis.
Parâmetros: path. Exemplo: dxf_audit(path="entrega.dxf")

## dxf_create

_mutating_

```python
dxf_create(path: 'str', units: 'str' = 'mm', version: 'str' = 'R2018', overwrite: 'bool' = False) -> 'dict[str, Any]'
```

Cria um DXF novo e vazio (com estilos de cota e tipos de linha padrão) sem abrir o AutoCAD.

QUANDO USAR: iniciar um desenho offline (esquema de suporte, folha de detalhe) para preencher com dxf_add_entities.
Parâmetros: path (.dxf); units (mm, cm, m, in, ft); version (R2000..R2018); overwrite (padrão false).
Exemplo: dxf_create(path="suporte-S12.dxf", units="mm")

## dxf_create_layer

_mutating_

```python
dxf_create_layer(path: 'str', name: 'str', color: 'int' = 7, linetype: 'str | None' = None, output_path: 'str | None' = None) -> 'dict[str, Any]'
```

Cria (ou confirma) uma camada em um DXF.

QUANDO USAR: preparar camadas (SUPORTES, COTAS, EIXOS) antes de desenhar.
Parâmetros: path; name; color (ACI 1-255); linetype (ex. "DASHED"); output_path (salva cópia, preserva o original).
Exemplo: dxf_create_layer(path="a.dxf", name="COTAS", color=3)

## dxf_add_entities

_mutating_

```python
dxf_add_entities(path: 'str', entities: 'list[dict[str, Any]]', layout: 'str | None' = None, output_path: 'str | None' = None) -> 'dict[str, Any]'
```

Adiciona em lote entidades a um DXF: line, circle, arc, polyline, text, mtext, point, ellipse, hatch, insert.

QUANDO USAR: desenhar offline. Valida tudo antes de salvar: se uma entidade falhar, nada é gravado.
Parâmetros: path; entities (lista de objetos com "type"); layout (omita para o modelo); output_path.
Campos: line{start,end} circle{center,radius} arc{center,radius,start_angle,end_angle} polyline{points,closed}
text{insert,text,height,rotation} mtext{insert,text,height} hatch{points,pattern,scale} insert{block,insert,attributes}
ellipse{center,major_axis,ratio}; todos aceitam layer e color (ACI).
Exemplo: dxf_add_entities(path="a.dxf", entities=[{"type":"line","start":[0,0],"end":[100,0],"layer":"EIXOS"}])

## dxf_define_block

_mutating_

```python
dxf_define_block(path: 'str', name: 'str', entities: 'list[dict[str, Any]]', attributes: 'list[str] | None' = None, output_path: 'str | None' = None) -> 'dict[str, Any]'
```

Define um bloco (com atributos opcionais) em um DXF para depois inserir com dxf_add_entities type=insert.

QUANDO USAR: criar o símbolo de suporte (ex. SUP-GUIA) com TAG/TIPO/LINHA offline.
Parâmetros: path; name; entities (mesmo formato de dxf_add_entities, sem hatch/insert aninhado recomendado);
attributes (lista de tags, ex. ["TAG","TIPO","LINHA"]); output_path.
Exemplo: dxf_define_block(path="a.dxf", name="SUP-GUIA", entities=[{"type":"circle","center":[0,0],"radius":50}], attributes=["TAG","TIPO"])

## dxf_modify_entities

_mutating_

```python
dxf_modify_entities(path: 'str', handles: 'list[str]', layer: 'str | None' = None, color: 'int | None' = None, translate: 'list[float] | None' = None, rotate_deg: 'float | None' = None, rotate_center: 'list[float] | None' = None, scale: 'float | None' = None, attributes: 'dict[str, str] | None' = None, output_path: 'str | None' = None) -> 'dict[str, Any]'
```

Altera entidades de um DXF: camada, cor, mover, girar, escalar e atributos de bloco.

QUANDO USAR: ajustes em lote de um DXF (mudar camada de suportes, deslocar um trecho, corrigir TAG).
Parâmetros: path; handles; layer; color; translate [dx,dy,dz]; rotate_deg (+ rotate_center); scale (>0);
attributes {"TAG":"S-01"} (só blocos); output_path (recomendado: salva cópia).
Exemplo: dxf_modify_entities(path="a.dxf", handles=["2A3"], attributes={"TIPO":"GUIA"}, output_path="a_rev1.dxf")

## dxf_delete_entities

_mutating_

```python
dxf_delete_entities(path: 'str', handles: 'list[str]', confirm: 'bool' = False, dry_run: 'bool' = False, output_path: 'str | None' = None) -> 'dict[str, Any]'
```

Apaga entidades de um DXF (exige confirm=true; dry_run mostra a prévia sem gravar).

QUANDO USAR: remover entidades erradas. Prefira output_path para manter o original.
Parâmetros: path; handles; confirm; dry_run; output_path.
Exemplo: dxf_delete_entities(path="a.dxf", handles=["2A3"], confirm=True, output_path="a_limpo.dxf")

## dxf_add_dimensions

_mutating_

```python
dxf_add_dimensions(path: 'str', dimensions: 'list[dict[str, Any]]', layout: 'str | None' = None, output_path: 'str | None' = None) -> 'dict[str, Any]'
```

Cota um DXF (cotagem): linear, alinhada, raio, diâmetro e angular, com bloco de cota nativo.

QUANDO USAR: cotar vãos, distâncias entre suportes, diâmetros de furo; gera cotas reais (entidade DIMENSION).
Parâmetros: path; dimensions (lista); layout; output_path. Campos comuns: layer, color, dimstyle (padrão "EZDXF"),
text_height, arrow_size, decimals, text (substitui o valor; "<>" = medida).
linear{base,p1,p2,angle} aligned{p1,p2,offset} radius{center,radius,angle} diameter{center,radius,angle}
angular{line1:[[x,y],[x,y]],line2:[[x,y],[x,y]],base}.
Exemplo: dxf_add_dimensions(path="a.dxf", dimensions=[{"kind":"linear","p1":[0,0],"p2":[1500,0],"base":[0,-200],"layer":"COTAS"}])

## dxf_create_layout

_mutating_

```python
dxf_create_layout(path: 'str', name: 'str', paper: 'str' = 'A3', landscape: 'bool' = True, margins_mm: 'float' = 10.0, viewports: 'list[dict[str, Any]] | None' = None, output_path: 'str | None' = None) -> 'dict[str, Any]'
```

Cria um layout (folha) de papel num DXF, com viewports que enquadram o modelo em escala.

QUANDO USAR: montar a folha de impressão antes de dxf_export (PDF).
Parâmetros: path; name; paper (A4, A3, A2, A1, A0); landscape; margins_mm; output_path;
viewports [{center:[x,y] no papel, width, height em mm, view_center:[x,y] no modelo, scale: papel/modelo (0.01 = 1:100)}].
Exemplo: dxf_create_layout(path="a.dxf", name="Folha1", paper="A3", viewports=[{"center":[210,148],"width":380,"height":260,"view_center":[750,0],"scale":0.1}])

## dxf_export

_mutating_

```python
dxf_export(path: 'str', output: 'str', layout: 'str | None' = None, dpi: 'int' = 150, background: 'str' = 'white') -> 'dict[str, Any]'
```

Renderiza o modelo ou um layout do DXF para PDF, PNG ou SVG, sem AutoCAD (motor ezdxf + matplotlib).

QUANDO USAR: gerar PDF de entrega ou imagem de pré-visualização; o formato vem da extensão de `output`.
Parâmetros: path; output (.pdf, .png ou .svg); layout (omita para o modelo); dpi (30-600); background ("white" = traço preto sobre branco, "default").
Exemplo: dxf_export(path="a.dxf", output="a.pdf", layout="Folha1")
Observação: é uma renderização aproximada (não idêntica ao plotter do AutoCAD).

## dxf_insert_support_symbol

_mutating_

```python
dxf_insert_support_symbol(path: 'str', kind: 'str', insert: 'list[float]', tag: 'str | None' = None, line: 'str | None' = None, size: 'float' = 100.0, layer: 'str | None' = None, output_path: 'str | None' = None) -> 'dict[str, Any]'
```

Insere um pictograma de suporte de tubulação (GUIA, ANCORA, APOIO, MOLA) com atributos TAG/TIPO/LINHA.

QUANDO USAR: montar offline o desenho/cadastro de suportes; o bloco SUP-<TIPO> é criado se ainda não existir
e depois pode ser lido com dxf_read_attributes. Os pictogramas são simplificados, não seguem uma norma.
Parâmetros: path; kind (GUIA, ANCORA, APOIO, MOLA); insert [x, y]; tag; line (nº da linha); size (largura do símbolo,
unidades do desenho; padrão 100); layer; output_path.
Exemplo: dxf_insert_support_symbol(path="a.dxf", kind="GUIA", insert=[1200, 0], tag="S-014", line="L-12", layer="SUPORTES")

## add_dimension

_mutating_

```python
add_dimension(kind: str, p1: list[float] | None = None, p2: list[float] | None = None, location: list[float] | None = None, center: list[float] | None = None, radius: float | None = None, angle_deg: float | None = None, vertex: list[float] | None = None, layer: str | None = None)
```

Cria uma cota nativa (entidade DIMENSION) no espaço modelo. Desfazível com um Ctrl+Z.

QUANDO USAR: cotar distâncias entre suportes, diâmetros, raios e ângulos direto no desenho aberto.
Parâmetros por tipo: linear (rotação por `angle_deg`: 0 = horizontal [padrão], 90 = vertical): p1, p2, location
(ponto por onde passa a linha de cota); aligned: p1, p2, location (ponto do texto); radius e diameter: center, radius,
angle_deg (direção do ponto na circunferência; padrão 45); angular: vertex, p1, p2, location (ponto do texto). layer opcional.
Exemplo: add_dimension(kind="linear", p1=[0,0], p2=[1500,0], location=[750,-200], layer="COTAS")
O estilo/tamanho vem do estilo de cota ativo do desenho (DIMSTYLE); a ferramenta não o altera.

## plot_to_pdf

_mutating_

```python
plot_to_pdf(path: str, layout: str | None = None, plot_extents: bool = True, overwrite: bool = False)
```

Plota o desenho aberto para PDF usando a impressora "DWG To PDF.pc3" do próprio AutoCAD (plotter real).

QUANDO USAR: gerar o PDF de entrega com a mesma fidelidade do comando PLOT; para PDF sem AutoCAD use dxf_export.
Parâmetros: path (.pdf, dentro das pastas permitidas); layout (nome; omita para o layout ativo; "Model" = modelo);
plot_extents (true = enquadra a extensão; false = usa a configuração salva do layout); overwrite (padrão false).
Exemplo: plot_to_pdf(path="C:/Users/eu/autocad-mcp-workspace/S12.pdf", layout="Folha1", overwrite=true)
Efeitos: desliga BACKGROUNDPLOT durante a plotagem (restaura depois) e pode mudar a configuração de plotagem do layout.

## project_data_set

_mutating_

```python
project_data_set(key: str, value: str)
```

Guarda um texto de projeto DENTRO do DWG (dicionário XRecord "AUTOCAD_MCP"), preservado ao salvar/abrir.

QUANDO USAR: registrar metadados do projeto no próprio desenho (revisão, nº do documento, norma, responsável).
Parâmetros: key (até 64 caracteres; sem espaços nas pontas), value (texto até 2000 caracteres).
Exemplo: project_data_set(key="REV", value="B - 2026-10-05")

## project_data_get

_read-only_

```python
project_data_get(key: str | None = None)
```

Lê dados de projeto gravados no DWG por project_data_set (uma chave ou todas).

QUANDO USAR: recuperar metadados do projeto guardados no desenho.
Parâmetros: key (omita para listar todas as chaves).
Exemplo: project_data_get(key="REV")
