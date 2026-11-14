# Disk Cleanup

Skill para agentes de IA analisarem o uso do disco, identificarem caches e arquivos grandes e ajudarem você a escolher o que remover. A análise começa em modo somente leitura; qualquer limpeza exige aprovação dos itens específicos.

O analisador roda localmente, lê apenas metadados e não possui modo de exclusão. Não usa serviços externos nem dependências além da biblioteca padrão do Python. Após a aprovação, o agente realiza a limpeza com as ferramentas e permissões do próprio ambiente.

## Requisitos

- **macOS ou Linux** para executar o analisador. Windows não é suportado.
- **Python 3.9+**, disponível como `python3`.
- Um agente compatível com Agent Skills, com acesso ao terminal e ao disco que será analisado.
- **Node.js 22.20+ e npm/npx** para instalar pelo CLI `skills`, conforme os [requisitos oficiais](https://github.com/vercel-labs/skills#install-a-skill). A instalação manual e o analisador não exigem Node.js.

## Instalação e uso nos harnesses

A skill usa o formato compartilhado Agent Skills: `SKILL.md` com `name` e `description`, acompanhado de um script Python independente. Pode ser usada em qualquer harness que carregue esse formato e permita executar Python e acessar o disco analisado.

### Pelo skills.sh

Execute no projeto em que deseja usar a skill e escolha o harness no instalador:

```sh
npx skills add th1ag0-Zz/disk-cleanup-agent --skill disk-cleanup
```

A instalação fica no projeto por padrão. Para disponibilizar a skill entre projetos, acrescente `--global`:

```sh
npx skills add th1ag0-Zz/disk-cleanup-agent --skill disk-cleanup --global
```

Todos os harnesses abaixo usam os mesmos arquivos e o mesmo fluxo de análise e aprovação. Para escolher o destino diretamente, acrescente `--agent` seguido do identificador da tabela.

| Harness | Identificador de `--agent` | Diretório no projeto | Diretório pessoal | Como invocar |
| --- | --- | --- | --- | --- |
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` | `/disk-cleanup` ou pelo nome na conversa |
| Codex | `codex` | `.agents/skills/` | `~/.agents/skills/` | `$disk-cleanup` ou pelo nome na conversa |
| Cursor | `cursor` | `.agents/skills/` | `~/.cursor/skills/` | Pelo nome na conversa |
| Gemini CLI | `gemini-cli` | `.agents/skills/` | `~/.gemini/skills/` | Pelo nome na conversa |
| GitHub Copilot | `github-copilot` | `.agents/skills/` | `~/.copilot/skills/` | Pelo nome na conversa |
| OpenCode | `opencode` | `.agents/skills/` | `~/.config/opencode/skills/` | Pelo nome na conversa |

Os destinos seguem a [lista de agentes suportados pelo CLI](https://github.com/vercel-labs/skills/blob/main/docs/agents.md). A tabela apresenta exemplos; para outro harness compatível, selecione-o no instalador ou consulte seu diretório de skills e sua forma de invocação. Veja também a [referência do CLI](https://github.com/vercel-labs/skills/blob/main/docs/commands.md).

As instruções e o analisador são compartilhados entre os harnesses. O arquivo `agents/openai.yaml` contém apenas metadados opcionais de interface; toda a lógica de uso está em `SKILL.md` e `scripts/analyze.py`.

Em sessões remotas ou containers, o relatório descreve o disco desse ambiente. Um chat sem acesso ao terminal e ao sistema de arquivos local não consegue analisar o disco do seu computador.

### Verificar e atualizar

Para verificar a instalação e manter as skills atualizadas:

```sh
npx skills list
npx skills list --global
npx skills update
```

`update` pode atualizar outras skills instaladas também. Se a skill não aparecer no agente, abra uma nova sessão e confira o destino escolhido na instalação.

### Instalação manual

Clone o repositório e entre na pasta:

```sh
git clone https://github.com/th1ag0-Zz/disk-cleanup-agent.git
cd disk-cleanup-agent
```

Escolha na tabela o diretório de skills do seu harness, no projeto ou na pasta pessoal. Para outros harnesses, consulte a documentação deles. Substitua o caminho de exemplo em `skill_destination` pelo destino escolhido e copie a pasta completa:

```sh
skill_destination="/caminho/do/diretorio/de/skills"
mkdir -p "$skill_destination"
cp -R skills/disk-cleanup "$skill_destination/"
```

Preserve a pasta `scripts/` junto de `SKILL.md`. Se já existir uma instalação, revise/substitua a versão antiga antes de copiar para evitar pastas aninhadas. A instalação manual não é gerenciada pelo CLI `skills`.

## Como usar

Peça ao agente para usar a skill pelo nome, ou utilize a invocação indicada na tabela. Os mesmos pedidos se aplicam a todos os harnesses:

```text
Use a skill disk-cleanup para analisar meu disco e mostrar o que posso remover.
```

```text
Use a skill disk-cleanup para listar arquivos acima de 1 GB em ~/Downloads.
```

```text
Analise o uso de disco com a skill disk-cleanup e apresente um relatório sem apagar nada.
```

O fluxo esperado é:

1. Analisar a pasta pessoal ou o diretório solicitado e informar espaço livre, maiores pastas, caches conhecidos e arquivos grandes.
2. Apresentar os candidatos com caminhos exatos, tamanhos estimados e consequências da remoção.
3. Abrir uma seleção no chat, permitir ajustes e apresentar os itens escolhidos para aprovação.
4. Revalidar os caminhos, remover somente os itens aprovados e medir o espaço livre novamente.

**Invocar a skill não autoriza apagar arquivos.** Você pode solicitar apenas a análise. Uma aprovação de caches não autoriza a remoção de arquivos pessoais ou de novos itens encontrados depois.

### Selecionar pelo chat

Ao terminar a análise, o agente apresenta os candidatos com números fixos, caminhos, tamanhos estimados e consequências. Se o chat disponibilizar uma ferramenta de seleção adequada, o agente usa essa interface. A aparência e o suporte a seleção múltipla dependem do harness; a skill não instala componentes de interface.

Nos demais ambientes, a interação funciona como um menu por texto, direto na conversa:

```text
Escolha o que deseja remover:
[ ] 1 | /example/.npm/_cacache | ~1,2 GiB | cache | exclusão permanente; exigirá novos downloads
[ ] 2 | /example/.cache/pip    | ~800 MiB | cache | exclusão permanente; exigirá novos downloads
Selecionados: nenhum
```

Você pode responder com:

| Resposta | Ação |
| --- | --- |
| `1, 2` ou `1-2` | Define a seleção pelos números exibidos. |
| `adicionar 2` / `remover 1` | Ajusta a seleção atual. |
| `detalhes 2` | Mostra as consequências de remover esse item. |
| `revisar` | Exibe os caminhos escolhidos, o total estimado e pede aprovação para apagar. |
| `cancelar` | Encerra sem apagar nada. |

Os marcadores `[ ]` do menu de texto são apenas visuais. A cada ajuste, o agente informa os itens selecionados e o total estimado. Selecionar não apaga: depois da revisão, responda explicitamente, por exemplo, `apagar os itens selecionados`. Se você já pediu a exclusão dos itens exatos apresentados, o agente aproveita essa aprovação sem repeti-la. Pedidos de relatório sem limpeza terminam na análise.

## Executar o analisador sem um agente

Na raiz do repositório clonado:

```sh
python3 skills/disk-cleanup/scripts/analyze.py --root "$HOME"
python3 skills/disk-cleanup/scripts/analyze.py --root "$HOME/Downloads" --min-size-mb 1024 --limit 20
python3 skills/disk-cleanup/scripts/analyze.py --help
```

| Opção | Padrão | Descrição |
| --- | --- | --- |
| `--root` | Pasta pessoal do usuário | Diretório a analisar. |
| `--min-size-mb` | `500` | Tamanho lógico mínimo em **MiB** para a lista de arquivos grandes. Aceita zero ou valores positivos. |
| `--limit` | `30` | Número máximo de arquivos grandes no relatório. Deve ser um inteiro positivo. |

O filtro de tamanho e o limite afetam apenas a lista de arquivos grandes; não reduzem a varredura nem os totais das pastas. Para uma análise mais rápida, escolha um `--root` menor. A varredura completa da pasta pessoal pode demorar e consumir memória proporcional à quantidade de arquivos.

A varredura percorre todas as pastas acessíveis dentro da raiz, inclusive as ocultas: Downloads, documentos, área de trabalho, fotos, vídeos, músicas, projetos, backups e dados de aplicativos. Não depende dos nomes dessas pastas nem de uma lista de ferramentas usadas pelo autor. A pasta pessoal é descoberta no ambiente de cada usuário; outras contas, diretórios do sistema e volumes externos não entram automaticamente no escopo.

A saída JSON vai para o terminal, com tamanhos em bytes:

| Campo | Conteúdo |
| --- | --- |
| `disk` | Espaço total, usado e livre do volume que contém a raiz analisada. |
| `scanned_allocated_bytes`, `files_scanned` | Espaço alocado e quantidade de arquivos contabilizados na varredura. |
| `top_directories` | Entradas do primeiro nível ordenadas pelo espaço alocado; também pode incluir arquivos desse nível. |
| `cache_candidates` | Caches conhecidos encontrados dentro do escopo, com tamanho alocado e indicador `scan_complete`. |
| `large_files` | Arquivos acima do limite mínimo, com tamanho lógico e alocado. |
| `scan_error_count`, `scan_errors` | Quantidade de erros e detalhes de até 100 ocorrências. |
| `skipped_symlinks`, `skipped_mounts` | Quantidade de links simbólicos ignorados e até 100 caminhos em outros sistemas de arquivos. |

O espaço usado do volume pode ser maior que o total analisado, pois a varredura cobre apenas o diretório escolhido. Revise erros e locais ignorados antes de considerar os resultados completos.

## Cuidados e limitações

### Caches de desenvolvimento

Além das pastas gerais de cache, o analisador reconhece estes locais dentro da pasta pessoal:

| Ferramenta | Caminhos reconhecidos |
| --- | --- |
| Next.js | `<projeto>/.next/cache` |
| Angular | `<projeto>/.angular/cache` |
| Vite | `<projeto>/node_modules/.vite` |
| Ferramentas JavaScript | `<projeto>/node_modules/.cache` |
| pytest, mypy e Ruff | `<projeto>/.pytest_cache`, `.mypy_cache`, `.ruff_cache` |
| Composer | `~/.composer/cache`, além das pastas gerais |
| NuGet | `~/.local/share/NuGet/v3-cache` e `plugins-cache` |

Os caches JavaScript exigem `package.json` na raiz do projeto; Angular exige `angular.json`. Os caches Python exigem um destes arquivos: `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt` ou `pytest.ini`. A verificação lê apenas metadados desses arquivos. Pastas com o mesmo nome, sem esse contexto, continuam sendo inventariadas e exigem classificação manual.

Nas pastas gerais, também há rótulos específicos para Go (`go-build`), Composer, Yarn, pnpm, node-gyp, Cypress e Poetry. Caches em locais personalizados não são descobertos automaticamente fora das regras descritas.

Os caminhos de [Next.js](https://nextjs.org/docs/app/guides/ci-build-caching), [Angular](https://angular.dev/cli/cache), [Vite](https://vite.dev/config/shared-options.html#cachedir) e [NuGet](https://learn.microsoft.com/en-us/nuget/consume-packages/managing-the-global-packages-and-cache-folders) seguem suas referências oficiais. Feche servidores e processos antes da limpeza: caches Next.js podem conter dados usados durante a execução; o cache pytest contém histórico de testes. Builds, ambientes virtuais, dependências completas, credenciais e sessões de agentes continuam exigindo revisão específica.

- Caches de aplicativos: descobre individualmente as entradas de `~/Library/Caches` e `~/.cache`, sem exigir uma lista de aplicativos. Entradas genéricas precisam de revisão do conteúdo antes de propor remoção.
- Caches de ferramentas: reconhece também Expo, Xcode, npm/npx, Gradle, Cargo, Rustup, Bun, Yarn e pnpm fora dessas pastas. Playwright, uv, pip, navegadores e outros aplicativos são identificados nas pastas gerais de cache. Podem exigir downloads ou recompilações após a remoção; ferramentas em uso devem ser fechadas antes.
- Arquivos grandes: apenas candidatos para decisão humana; tamanho não significa que podem ser apagados.
- Docker, emuladores e SDKs: precisam de inspeção própria. Volumes podem conter bancos de dados.
- Projetos e arquivos pessoais: nunca classificados automaticamente como descartáveis.

Durante a varredura, links simbólicos e entradas em outros sistemas de arquivos são ignorados. A raiz fornecida é resolvida antes da análise. Permissões negadas aparecem no relatório; os totais podem ser parciais. Não há elevação automática de privilégios.

Arquivos com hard links são contados uma vez. APFS, snapshots, arquivos esparsos e arquivos abertos podem alterar o espaço realmente recuperado. A soma dos tamanhos dos candidatos é uma estimativa; o resultado da limpeza deve ser conferido pela variação medida de espaço livre.

A identificação automática de caches se restringe à pasta pessoal do usuário atual e ao escopo analisado. Respeita também `XDG_CACHE_HOME` quando for um caminho absoluto dentro dessa pasta pessoal; valores relativos ou externos não ampliam o escopo. Outras localizações personalizadas são inventariadas quando dentro da raiz, mas precisam de classificação manual. Os candidatos não incluem alvos sobrepostos. Erros, links ou volumes ignorados fazem os tamanhos dos candidatos serem marcados como estimativas incompletas.

## Privacidade

O analisador não lê o conteúdo dos arquivos nem transmite dados. A saída contém caminhos e nomes locais: revise antes de compartilhar ou enviar ao GitHub. Ao usar um agente de IA, os resultados podem entrar no contexto desse agente e ficam sujeitos às políticas dele.

O CLI `skills` é uma ferramenta externa, com sua própria [política de telemetria](https://github.com/vercel-labs/skills#telemetry). Não publique relatórios reais, tokens ou arquivos pessoais em issues, exemplos ou pull requests.

## Estrutura do repositório

```text
skills/disk-cleanup/
├── SKILL.md             # Instruções e regras de aprovação para o agente
├── agents/openai.yaml   # Metadados opcionais de interface OpenAI
└── scripts/analyze.py   # Analisador local, somente leitura
tests/test_analyze.py    # Testes do analisador
LICENSE                 # Licença MIT
README.md
```

## Desenvolvimento

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Os testes usam apenas arquivos temporários e verificam preservação dos dados, links simbólicos, hard links, arquivos esparsos, classificação de caches e erros de permissão. Também executam o analisador instalado em `.claude/skills` e `.agents/skills`, por cópia e link simbólico, a partir de outro diretório e com espaços nos caminhos. Não é necessário instalar dependências Python.

Para contribuir, abra uma issue ou pull request com o comportamento esperado, sistema operacional e passos de reprodução. Use exemplos fictícios e execute os testes ao alterar o analisador. Preserve a análise somente leitura e a aprovação de itens específicos antes de qualquer exclusão.

## Licença

[MIT](LICENSE).
