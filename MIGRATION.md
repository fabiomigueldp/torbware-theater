# Guia de Migração e Novas Funcionalidades

Este documento detalha as mudanças introduzidas na nova versão do Theater, com foco na padronização de metadados e no pipeline de legendas aprimorado. Siga as instruções abaixo para atualizar sua biblioteca e entender as novas funcionalidades.

## Sumário das Mudanças

1.  **Padronização de Metadados para Inglês**: Todos os metadados de filmes (título, descrição, etc.) agora são buscados e armazenados em inglês (`en-US`). O campo `title` e `original_title` no `metadata.json` serão idênticos.
2.  **Busca de Legendas Aprimorada**: A busca de legendas agora utiliza o `original_title` do filme, resultando em correspondências mais precisas.
3.  **Fallback de Legendas PT-BR**: Se nenhuma legenda em português for encontrada nos provedores padrão, o sistema automaticamente fará uma busca adicional no **Podnapisi** para garantir a disponibilidade de legendas em PT-BR.
4.  **Normalização e Ordenação de Legendas**: Os códigos de idioma das legendas são normalizados (ex: `por`, `pb` -> `pt-BR`). A lista de legendas é sempre ordenada da seguinte forma: **Português (Brasil)**, **English**, e demais idiomas em ordem alfabética.
5.  **Exibição no Front-End**: A interface agora exibe o `original_title`, garantindo consistência com os metadados padronizados.

---

## 1. Como Rodar o Script de Migração

Para garantir que sua biblioteca existente seja compatível com o novo padrão, você **deve** rodar o script de migração. Ele fará as seguintes alterações nos seus arquivos `metadata.json`:

*   Garantirá que `title` e `original_title` sejam idênticos.
*   Adicionará o campo `year` se ele não existir.
*   Normalizará os códigos de idioma, URLs, e ordenará as legendas.

**Passos:**

1.  **Navegue até a raiz do projeto** no seu terminal.
2.  **Execute o script** com o seguinte comando:
    ```bash
    python scripts/migrate_library_metadata.py
    ```
3.  O script pedirá uma **confirmação** antes de modificar os arquivos. Digite `s` e pressione Enter para continuar.
4.  Para cada filme modificado, um backup do metadado original será criado (ex: `metadata.json.bak`). Após verificar que a migração ocorreu com sucesso, você pode remover esses backups.

---

## 2. Como Rodar os Testes

Para verificar a integridade da aplicação e a correta implementação das novas funcionalidades, você pode rodar a suíte de testes.

**Passos:**

1.  **Instale as dependências de teste** (se ainda não o fez):
    ```bash
    pip install pytest
    pip install -r worker/requirements.txt
    ```
2.  **Execute o Pytest** a partir da raiz do projeto:
    ```bash
    pytest tests/
    ```
3.  Todos os testes devem passar, indicando que o ambiente está configurado corretamente.

---

## 3. Feature Flag: `ORIGINAL_METADATA_ONLY` (Opcional)

Para desenvolvedores ou casos de uso específicos onde o comportamento antigo (metadados em `pt-BR`) é desejado temporariamente, uma variável de ambiente foi disponibilizada.

*   **`ORIGINAL_METADATA_ONLY=true`** (Padrão): Força a busca de metadados em inglês.
*   **`ORIGINAL_METADATA_ONLY=false`**: Reverte para o comportamento antigo, buscando metadados em português.

Esta flag **não** desativa o fallback de legendas PT-BR, que é uma funcionalidade separada e sempre ativa.

Para usar, defina a variável de ambiente no seu arquivo `.env` ou ao iniciar o worker.

---

## 4. Checklist de Validação Pós-Deploy

Após a migração e o deploy da nova versão, verifique os seguintes pontos para garantir que tudo está funcionando como esperado:

-   [ ] **Novos Filmes**: Adicione um novo filme e verifique se o `metadata.json` gerado contém o `title` e `original_title` em inglês.
-   [ ] **Biblioteca**: Confirme que a biblioteca no front-end está ordenada alfabeticamente pelo título original em inglês.
-   [ ] **Legendas**:
    -   Abra um filme e verifique se as opções de legenda estão na ordem correta (`pt-BR`, `en`, ...).
    -   Teste um filme que **não tinha** legenda em português anteriormente para confirmar se o fallback do Podnapisi foi acionado e encontrou uma.
-   [ ] **Player**: Verifique se o título exibido no player é o título em inglês.
-   [ ] **Logs**: Monitore os logs do worker para ver as mensagens sobre a busca de metadados e o acionamento do fallback de legendas.
