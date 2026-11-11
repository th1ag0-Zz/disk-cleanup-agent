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
3. Pedir aprovação de uma seleção concreta de itens.
4. Revalidar os caminhos, remover somente os itens aprovados e medir o espaço livre novamente.

**Invocar a skill não autoriza apagar arquivos.** Você pode solicitar apenas a análise. Uma aprovação de caches não autoriza a remoção de arquivos pessoais ou de novos itens encontrados depois.

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

- Caches conhecidos: Playwright, Expo, Xcode, uv, npm/npx e pip. Exigem downloads ou recompilações após a remoção; ferramentas em uso devem ser fechadas antes.
- Arquivos grandes: apenas candidatos para decisão humana; tamanho não significa que podem ser apagados.
- Docker, emuladores e SDKs: precisam de inspeção própria. Volumes podem conter bancos de dados.
- Projetos e arquivos pessoais: nunca classificados automaticamente como descartáveis.

Durante a varredura, links simbólicos e entradas em outros sistemas de arquivos são ignorados. A raiz fornecida é resolvida antes da análise. Permissões negadas aparecem no relatório; os totais podem ser parciais. Não há elevação automática de privilégios.

Arquivos com hard links são contados uma vez. APFS, snapshots, arquivos esparsos e arquivos abertos podem alterar o espaço realmente recuperado. A soma dos tamanhos dos candidatos é uma estimativa; o resultado da limpeza deve ser conferido pela variação medida de espaço livre.

A identificação automática de caches cobre apenas caminhos conhecidos na pasta pessoal do usuário atual, dentro do escopo analisado. Não cobre todas as aplicações nem diretórios personalizados.

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

## Publicação no skills.sh

Para quem mantém este repositório:

1. Publique os arquivos no repositório público [th1ag0-Zz/disk-cleanup-agent](https://github.com/th1ag0-Zz/disk-cleanup-agent).
2. Preserve `skills/disk-cleanup/SKILL.md` e os arquivos da skill. O layout `skills/<nome>/SKILL.md` é [descoberto pelo CLI](https://github.com/vercel-labs/skills/blob/main/docs/creating-skills.md); o frontmatter já contém `name` e `description`.
3. Confira a descoberta sem instalar e, em seguida, teste a instalação usando a origem pública:

   ```sh
   npx skills add th1ag0-Zz/disk-cleanup-agent --list
   npx skills add th1ag0-Zz/disk-cleanup-agent --skill disk-cleanup
   ```

Segundo a [FAQ do skills.sh](https://skills.sh/docs/faq), a listagem ocorre automaticamente a partir das instalações registradas pela telemetria do CLI. Não é necessário publicar um pacote npm nem fazer uma submissão manual ao diretório.

## Licença

[MIT](LICENSE).
