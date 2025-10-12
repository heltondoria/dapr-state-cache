# Especificação Técnica - dapr-state-cache

## 1. Visão Geral e Objetivos

### 1.1 Propósito da Biblioteca

A biblioteca `dapr-state-cache` é uma solução de cache genérica baseada em Dapr State Store, projetada para reuso cross-layer (web, workers, jobs) com foco em robustez e performance. A biblioteca implementa um sistema de cache transparente que funciona com funções síncronas e assíncronas, métodos de instância, métodos de classe e métodos estáticos.

### 1.2 Casos de Uso Principais

- **Cache de APIs**: Cache de respostas de APIs externas com TTL configurável
- **Cache de Dados Computacionais**: Cache de resultados de operações custosas
- **Cache de Configurações**: Cache de configurações de aplicação
- **Cache de Métodos de Serviço**: Cache de métodos de classes de serviço
- **Cache Cross-Layer**: Compartilhamento de cache entre diferentes camadas da aplicação

### 1.3 Requisitos Não-Funcionais

- **Robustez**: Chaves determinísticas, deduplicação de cache miss, fallbacks em caso de falha
- **Performance**: Read-through, write-through, operações sob demanda
- **Segurança**: Fallbacks, timeouts, operações best-effort (falhas não quebram o fluxo)
- **Observabilidade**: Hooks para métricas, tracing e logging
- **Extensibilidade**: Serializers pluggáveis, key builders flexíveis

## 2. Arquitetura do Sistema

### 2.1 Componentes Principais

```text
dapr_state_cache/
├── decorators/         # @cacheable, invalidation helpers
├── keys/               # Key builders, normalização, hashing
├── codecs/             # Serializers (JSON/msgpack/pickle)
├── backend/            # DaprStateBackend (único)
├── orchestration/      # Deduplicação
└── observability/      # Hooks para métricas/tracing
```

### 2.2 Fluxo de Dados e Ciclo de Vida

1. **Geração de Chave**: `key_prefix:function_name:hash(args)`
2. **Cache Lookup**: Busca no Dapr State Store
3. **Cache Hit**: Retorna dados deserializados (e descriptografados se crypto habilitado)
4. **Cache Miss**: Deduplica chamadas concorrentes para mesma chave
5. **Compute**: Executa função original com timeout configurável
6. **Cache Write**: Serializa → Criptografa (se habilitado) → Armazena com ttlInSeconds

### 2.3 Padrões Arquiteturais

- **Decorator Pattern**: Para transparência no uso do cache
- **Strategy Pattern**: Para serializers e key builders
- **Observer Pattern**: Para hooks de observabilidade
- **Protocol Pattern**: Para extensibilidade e type safety
- **Chain of Responsibility**: Para pipeline de serialização → criptografia → storage

## 3. Valores Padrão e Configurações

### 3.1 Parâmetros do Decorator @cacheable

A API simplificada do decorator `@cacheable` possui 10 parâmetros essenciais:

```python
@cacheable(
    # Parâmetros Essenciais
    store_name: str = "cache",                         # Nome do store Dapr
    ttl_seconds: int | None = None,                    # TTL em segundos (None = default 3600)
    key_prefix: str = "cache",                         # Prefixo das chaves
    
    # Parâmetros de Customização
    key_builder: KeyBuilder | None = None,             # Construtor de chaves customizado
    serializer: Serializer | None = None,              # Serializer customizado
    use_dapr_crypto: bool = False,                     # Usar Dapr Cryptography
    crypto_component_name: str | None = None,          # Nome do componente de criptografia
    
    # Parâmetros de Controle
    condition: Callable | None = None,                 # Condição para cachear
    bypass: Callable | None = None,                    # Condição para ignorar cache
    hooks: ObservabilityHooks | None = None            # Hooks de observabilidade
)
```

#### Tabela de Parâmetros

| Parâmetro                  | Tipo                       | Padrão   | Descrição                                                                  |
|----------------------------|----------------------------|----------|----------------------------------------------------------------------------|
| `store_name`               | str                        | "cache"  | Nome do store Dapr (sobrescrito por `DAPR_CACHE_DEFAULT_STORE_NAME`)      |
| `ttl_seconds`              | int \| None                | None     | TTL em segundos (None usa default de 3600s)                                |
| `key_prefix`               | str                        | "cache"  | Prefixo das chaves                                                         |
| `key_builder`              | KeyBuilder \| None         | None     | Construtor de chaves customizado (usa DefaultKeyBuilder)                   |
| `serializer`               | Serializer \| None         | None     | Serializer customizado (usa JsonSerializer)                                |
| `use_dapr_crypto`          | bool                       | False    | Usar Dapr Cryptography building block                                      |
| `crypto_component_name`    | str \| None                | None     | Nome do componente de criptografia (sobrescrito por `DAPR_CACHE_DEFAULT_CRYPTO_NAME`) |
| `condition`                | Callable \| None           | None     | Condição para cachear (deve retornar True para cachear)                    |
| `bypass`                   | Callable \| None           | None     | Condição para ignorar cache (deve retornar True para ignorar)              |
| `hooks`                    | ObservabilityHooks \| None | None     | Hooks de observabilidade                                                   |

**Configuração via Variáveis de Ambiente**:

- `store_name` pode ser configurado via `DAPR_CACHE_DEFAULT_STORE_NAME`
- `crypto_component_name` pode ser configurado via `DAPR_CACHE_DEFAULT_CRYPTO_NAME`

**Ordem de Precedência para `store_name`**:

1. **Valor explícito no decorator** (maior precedência)
2. **Variável de ambiente** `DAPR_CACHE_DEFAULT_STORE_NAME`
3. **Default** `"cache"` (menor precedência)

**Ordem de Precedência para `crypto_component_name`** (quando `use_dapr_crypto=True`):

1. **Valor explícito no decorator via parâmetro `crypto_component_name`** (maior precedência)
2. **Variável de ambiente** `DAPR_CACHE_DEFAULT_CRYPTO_NAME`
3. **Default** `"cache-crypto"` (menor precedência)

**Exemplos**:

```python
# Cenário 1: Usa store explícito "users"
@cacheable(store_name="users")

# Cenário 2: Usa env DAPR_CACHE_DEFAULT_STORE_NAME="prod-cache"
@cacheable()  # store_name será "prod-cache"

# Cenário 3: Usa defaults
@cacheable()  # store_name será "cache"

# Cenário 4: Criptografia com componente explícito
@cacheable(use_dapr_crypto=True, crypto_component_name="my-crypto")

# Cenário 5: Criptografia com componente customizado via env
# DAPR_CACHE_DEFAULT_CRYPTO_NAME="my-crypto"
@cacheable(use_dapr_crypto=True)  # usará componente "my-crypto"

# Cenário 6: Criptografia com default
@cacheable(use_dapr_crypto=True)  # usará componente "cache-crypto"
```

### 3.2 Serializers

| Serializer            | Dependência | Uso Recomendado          |
|-----------------------|-------------|--------------------------|
| `JsonSerializer`      | Padrão      | Dados JSON-serializáveis |
| `MsgpackSerializer`   | `msgpack`   | Dados binários compactos |
| `PickleSerializer`    | Padrão      | Objetos Python nativos   |

## 4. Regras de Geração de Chaves

### 4.1 Algoritmo de Geração de Chaves

A biblioteca implementa um sistema simplificado de geração de chaves de cache:

1. **Path Completo da Função**: Captura módulo, classe (se aplicável) e nome da função
2. **Valores dos Parâmetros**: Serializa todos os argumentos (posicionais e nomeados)
3. **Hash Não-Colidível**: Aplica função hash (SHA256) sobre path + parâmetros serializados
4. **Key Builder Customizado**: Usuário pode fornecer função customizada via parâmetro `key_builder`
5. **Determinismo**: Ordenação de kwargs e normalização de tipos garantem hash estável

### 4.2 Hash Determinístico

- **Algoritmo**: SHA256 sobre representação serializada do path da função + argumentos
- **Path da Função**: `module.class.function` (ou `module.function` para funções standalone)
- **Serialização de Argumentos**: Conversão recursiva para tipos JSON-serializáveis com normalização
- **Estabilidade**: Hash idêntico para mesmos argumentos independente da ordem
- **Formato da Chave**: `{key_prefix}:{function_path}:{hash}`

### 4.3 Key Builder Customizado

Usuários podem fornecer uma função customizada para gerar chaves de cache:

```python
from dapr_state_cache import cacheable, KeyBuilder

class CustomKeyBuilder(KeyBuilder):
    def build_key(self, func, args, kwargs) -> str:
        # Lógica customizada de geração de chave
        return f"custom:{func.__name__}:{hash(args)}"

@cacheable(key_builder=CustomKeyBuilder())
def my_function(x: int) -> int:
    return x * 2
```

**Comportamento**:

- Se `key_builder` não for fornecido, usa `DefaultKeyBuilder` interno
- Key builder customizado deve implementar o Protocol `KeyBuilder`
- Permite controle total sobre geração de chaves
- Útil para casos com requisitos específicos de identidade

#### 4.3.1 Protocol KeyBuilder

A biblioteca define o Protocol `KeyBuilder` para extensibilidade de geração de chaves:

```python
from typing import Protocol, Callable

class KeyBuilder(Protocol):
    """Protocol para construtores de chaves de cache customizados."""
    
    def build_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """
        Constrói uma chave de cache a partir da função e seus argumentos.
        
        Args:
            func: Função decorada
            args: Argumentos posicionais
            kwargs: Argumentos nomeados
            
        Returns:
            Chave de cache como string
        """
        ...
```

**Nota**: Esta é a estrutura básica do Protocol. Detalhes de implementação e validações serão definidos durante a implementação da biblioteca.

## 5. Políticas de Cache

### 5.1 TTL (Time To Live) e Expiração

- **TTL Nativo do Dapr**: Usa `ttlInSeconds` como metadata do Dapr State Store
- **Hard TTL**: Expiração automática gerenciada pelo Dapr State Store
- **TTL Default**: Quando `ttl_seconds=None`, usa default de 3600 segundos (1 hora)
- **Sem Expiração**: Cache permanente não é suportado - sempre requer TTL >= 1
- **Validação**: `ttl_seconds` deve ser inteiro >= 1, ou None (usa default de 3600)
- **TTL Zero Inválido**: `ttl_seconds=0` lança `ValueError`
- **State Stores Compatíveis**: Redis, MongoDB, PostgreSQL, Cosmos DB, etc. ([ver lista completa](https://docs.dapr.io/reference/components-reference/supported-state-stores/))
- **Referência**: [Documentação TTL do Dapr](https://docs.dapr.io/developing-applications/building-blocks/state-management/state-store-ttl/)

### 5.2 Condições de Cache

- **condition**: Função que determina se deve cachear (retorna True para cachear)
- **bypass**: Função que determina se deve ignorar cache (retorna True para ignorar)

### 5.3 Armazenamento Simplificado

Dados são armazenados diretamente no Dapr State Store:

- **Serialização**: Dados originais serializados pelo serializer configurado
- **Criptografia**: Opcional via Dapr Cryptography building block
- **TTL**: Gerenciado nativamente pelo state store via `ttlInSeconds`
- **Sem Envelope**: Não há necessidade de metadados adicionais
- **Performance**: Overhead mínimo sem envelope

## 6. Orquestração e Otimizações

### 6.1 Deduplicação de Cache Miss (Thundering Herd)

- **Problema**: Múltiplas chamadas simultâneas para mesma chave causam múltiplas computações
- **Solução**: Sistema de futures compartilhadas por chave
- **Implementação**: `DeduplicationManager` com lock assíncrono
- **Benefício**: Evita computações redundantes e reduz carga no sistema

**Detalhes do DeduplicationManager**:

- **Estrutura**: Mantém `Dict[str, asyncio.Future]` de futures por chave
- **Lock**: Lock assíncrono global para operações de registro/limpeza
- **Comportamento**:
  1. Primeira chamada para uma chave cria e registra future
  2. Chamadas concorrentes para mesma chave aguardam a mesma future
  3. Após computação, resultado é compartilhado com todas chamadas aguardando
  4. Future é removida do registro após conclusão
- **Thread Safety**: Operações atômicas via asyncio.Lock
- **Garbage Collection**: Futures são automaticamente limpas após uso

**Tratamento de Exceções**:

- **Se computação lança exceção**: Future é resolvida com a exceção
- **Propagação**: Todas chamadas aguardando recebem a mesma exceção
- **Limpeza**: Future é removida do registro após falha
- **Retry**: Próxima chamada para mesma chave tenta novamente (não há cache de falhas)
- **Observabilidade**: Erros são registrados via hooks `on_cache_error` quando configurados

### 6.2 Modelo Read-Through/Write-Through

- **Read-Through**: Cache miss executa função e armazena resultado
- **Write-Through**: Escritas vão para cache e backend simultaneamente
- **Simplicidade**: Sem refresh proativo, apenas operações sob demanda
- **Performance**: Overhead mínimo sem operações em background

## 7. Resiliência e Fallbacks

### 7.1 Tratamento de Erros Simplificado

- **Falhas de Backend**: Log de erro + bypass do cache (executa função normalmente)
- **Falhas de Serialização**: Log de erro + bypass do cache
- **Falhas de Criptografia**: Log de erro + bypass do cache
- **Best-Effort**: Operações de cache não quebram o fluxo principal
- **Observabilidade**: Hooks de erro para monitoramento
- **Resiliência do Dapr**: Timeout, retry e circuit breaker delegados ao [Dapr Resiliency](https://docs.dapr.io/operations/resiliency/) (configurado externamente via políticas de resiliência)

### 7.2 Best-Effort e Tratamento de Erros

- **Serialização**: Falhas de serialização não quebram o fluxo
- **Backend**: Falhas de backend não impedem execução da função
- **Invalidação**: Operações de invalidação são best-effort
- **Logging**: Erros são logados mas não propagados

### 7.3 Política de Tratamento de Erros

A biblioteca implementa uma política clara de tratamento de erros, distinguindo entre erros recuperáveis e irrecuperáveis:

#### 7.3.1 Erros Recuperáveis (Best-Effort)

Erros recuperáveis não impedem o fluxo da aplicação. A biblioteca registra o erro e continua sem a funcionalidade afetada:

**Comportamento**:

- Log de erro detalhado (nível ERROR)
- Notificação via hook `on_cache_error` (quando configurado)
- Continua execução sem a funcionalidade afetada
- Não propaga exceção para aplicação

**Exemplos de Erros Recuperáveis**:

- **Falha de Serialização**: Cache miss + executa função + retorna resultado sem cachear
- **Falha de Criptografia no Write**: Log erro + cache sem criptografar (dados em plaintext)
- **Falha de Descriptografia no Read**: Log erro + cache miss + recomputação
- **Componente de Criptografia Não Configurado**: Log erro + todas operações sem criptografia
- **Timeout no Cache Read**: Log erro + cache miss + executa função
- **Timeout no Cache Write**: Log erro + retorna resultado sem cachear
- **Falha de Invalidação**: Log erro + operação falha gracefully

#### 7.3.2 Erros Irrecuperáveis

Erros irrecuperáveis indicam problemas críticos de infraestrutura. A biblioteca registra o erro e propaga a exceção:

**Comportamento**:

- Log de erro crítico (nível CRITICAL)
- Notificação via hook `on_cache_error` (quando configurado)
- Propaga exceção para aplicação
- Aplicação deve decidir como lidar

**Exemplos de Erros Irrecuperáveis**:

- **DaprClient não disponível**: Dapr sidecar não está rodando ou inacessível
- **State Store não configurado**: Store name não existe na configuração do Dapr
- **Erro de autenticação**: Credenciais inválidas para state store subjacente
- **Erro de rede crítico**: Falha de conexão persistente com Dapr

#### 7.3.3 Responsabilidade do Dapr

A biblioteca delega comportamentos de resiliência ao Dapr:

- **Timeout**: Configurado via [Dapr Resiliency policies](https://docs.dapr.io/operations/resiliency/)
- **Retry**: Configurado via Dapr Resiliency policies
- **Circuit Breaker**: Configurado via Dapr Resiliency policies
- **Bulkhead**: Configurado via Dapr Resiliency policies

**Configuração Externa**: Políticas de resiliência são configuradas no arquivo de resiliência do Dapr, não como parâmetros da biblioteca.

#### 7.3.4 Observabilidade de Erros

Todos os erros (recuperáveis e irrecuperáveis) são registrados:

- **Logs**: Mensagens detalhadas com contexto (chave, operação, stack trace)
- **Hooks**: Hook `on_cache_error(key, error)` chamado para todos os erros
- **Métricas**: Contador de erros incrementado (quando sistema de métricas configurado)
- **Tracing**: Span marcado com erro (quando tracing configurado)

## 8. Serialização e Codecs

### 8.1 Estratégia de Normalização de Tipos

A biblioteca implementa um sistema de normalização de tipos Python para garantir serialização consistente:

**Tipos Suportados Nativamente**:

| Tipo Python    | Conversão                         | Exemplo                                      |
|----------------|-----------------------------------|----------------------------------------------|
| `datetime`     | ISO 8601 string                   | `"2025-10-11T14:30:00Z"`                     |
| `date`         | ISO 8601 string                   | `"2025-10-11"`                               |
| `time`         | ISO 8601 string                   | `"14:30:00"`                                 |
| `Decimal`      | string                            | `"123.45"`                                   |
| `UUID`         | string                            | `"550e8400-e29b-41d4-a716-446655440000"`     |
| `bytes`        | base64 string                     | `"SGVsbG8gV29ybGQ="`                         |
| `set`          | list (ordenado)                   | `[1, 2, 3]`                                  |
| `frozenset`    | list (ordenado)                   | `[1, 2, 3]`                                  |

**Comportamento**:

- **Tipos Comuns**: Biblioteca fornece serializadores para tipos comuns acima
- **Serializadores Customizados**: Usuário pode fornecer serializador customizado via parâmetro `serializer`
- **Erro para Tipos Não Suportados**: Tipos não serializáveis sem serializador customizado lançam `TypeError` explícito
- **Extensibilidade**: Protocol `Serializer` permite implementações customizadas
- **Determinismo**: Sets são ordenados antes de conversão para garantir hash estável

### 8.2 Serializers Suportados

- **JsonSerializer**: Serialização JSON com normalizadores
- **MsgpackSerializer**: Serialização binária compacta (opcional)
- **PickleSerializer**: Serialização Python nativa (opcional)
- **Extensibilidade**: Protocol Serializer para implementações customizadas

### 8.3 Extensibilidade

- **Protocol Serializer**: Interface para serializers customizados
- **Registry Pattern**: Para normalizadores de tipos
- **Pluggable**: Fácil substituição de componentes

### 8.4 Criptografia via Dapr

A biblioteca integra com o building block de criptografia do Dapr para operações de criptografia e descriptografia:

#### 8.4.1 Integração com Dapr Cryptography

- **Building Block**: Usa o Dapr Cryptography API nativo
- **Componentes Suportados**: Azure Key Vault, AWS KMS, GCP KMS, Local Storage
- **Parâmetro**: `use_dapr_crypto: bool = False` no `@cacheable`
- **Fluxo de Dados**:
  1. **Write**: `Dados → Serializer → Dapr Cryptography → Backend`
  2. **Read**: `Backend → Dapr Cryptography → Deserializer → Dados`

#### 8.4.2 Configuração do Dapr Cryptography

**Nome do Componente**: Segue ordem de precedência similar ao `store_name`:

1. **Parâmetro explícito** via `crypto_component_name`
2. **Variável de ambiente** `DAPR_CACHE_DEFAULT_CRYPTO_NAME`
3. **Default** `"cache-crypto"`

**Componentes Suportados**: Azure Key Vault, AWS KMS, GCP KMS e Local Storage conforme [documentação oficial do Dapr](https://docs.dapr.io/developing-applications/building-blocks/cryptography/).

**Tratamento de Erros (Erros Recuperáveis)**:

A biblioteca implementa política de fallback para erros de criptografia, tratando-os como recuperáveis (ver seção 7.3.1):

- **Componente não configurado**: Se `use_dapr_crypto=True` mas componente não existe no Dapr
  - Log de erro (nível ERROR)
  - Todas operações continuam sem criptografia (dados em plaintext)
  - Hook `on_cache_error` notificado
  - Aplicação continua normalmente
  
- **Falha de criptografia no Write**: Durante operação de cache write
  - Log de erro (nível ERROR)
  - Cache armazena dados sem criptografia (plaintext)
  - Hook `on_cache_error` notificado
  - Operação de cache completa normalmente
  
- **Falha de descriptografia no Read**: Durante operação de cache read
  - Log de erro (nível ERROR)
  - Tratado como cache miss
  - Função é executada e resultado retornado
  - Hook `on_cache_error` notificado
  - Próximo write tenta criptografar novamente

#### 8.4.3 Exemplo de Uso

```python
from dapr_state_cache import cacheable

# Exemplo 1: Criptografia com componente explícito
@cacheable(
    store_name="sensitive-cache",
    use_dapr_crypto=True,
    crypto_component_name="production-kms",
    ttl_seconds=300
)
async def get_user_token(user_id: int) -> str:
    return await fetch_sensitive_token(user_id)  # função fictícia para exemplo

# Exemplo 2: Criptografia com default
@cacheable(
    store_name="sensitive-cache",
    use_dapr_crypto=True,
    ttl_seconds=300
)
async def get_api_key(api_id: str) -> str:
    return await fetch_api_key(api_id)  # função fictícia para exemplo
```

#### 8.4.4 Considerações de Segurança

- **Encryption-at-Rest**: Para dados sensíveis (PII, tokens, etc.)
- **Performance**: Overhead mínimo usando Dapr nativo
- **Key Management**: Gerenciado pelo Dapr e componentes configurados
- **Recomendações**: Use componentes KMS para produção

**Referência**: [Dapr Cryptography Documentation](https://docs.dapr.io/developing-applications/building-blocks/cryptography/)

### 8.5 Protocol Serializer

A biblioteca define o Protocol `Serializer` para extensibilidade de serialização:

```python
from typing import Protocol, Any

class Serializer(Protocol):
    """Protocol para serializers customizados."""
    
    def serialize(self, data: Any) -> bytes:
        """
        Serializa dados Python para bytes.
        
        Args:
            data: Dados a serem serializados
            
        Returns:
            Dados serializados como bytes
            
        Raises:
            TypeError: Se dados não são serializáveis
        """
        ...
    
    def deserialize(self, data: bytes) -> Any:
        """
        Deserializa bytes para dados Python.
        
        Args:
            data: Bytes serializados
            
        Returns:
            Dados Python deserializados
            
        Raises:
            ValueError: Se dados estão corrompidos ou inválidos
        """
        ...
```

**Nota**: Esta é a estrutura básica do Protocol. Detalhes de implementação, normalizadores de tipos e validações serão definidos durante a implementação da biblioteca.

## 9. Observabilidade

### 9.1 Hooks de Eventos

- **Cache Hit**: Notificação de acertos com latência
- **Cache Miss**: Notificação de falhas com latência
- **Cache Write**: Notificação de escritas com tamanho dos dados
- **Cache Error**: Notificação de erros com exceção

### 9.2 Sistema de Métricas

- **Estatísticas Gerais**: Hits, misses, writes, errors, latências
- **Estatísticas por Chave**: Métricas individuais por chave
- **Taxa de Acerto**: Hit ratio calculado automaticamente
- **Latências**: Médias de latência para hits e misses
- **Top Keys**: Chaves mais acessadas por critério

### 9.3 Estatísticas por Chave

- **Tracking Individual**: Cada chave tem suas próprias estatísticas
- **Agregação**: Estatísticas gerais são agregações das individuais
- **Ordenação**: Suporte a ordenação por hits, misses, writes, errors
- **Top Keys**: Chaves mais acessadas podem ser consultadas por critério (hits, misses, writes, errors)

### 9.4 Protocol ObservabilityHooks

A biblioteca define o Protocol `ObservabilityHooks` para integração com sistemas de observabilidade:

```python
from typing import Protocol

class ObservabilityHooks(Protocol):
    """Protocol para hooks de observabilidade customizados."""
    
    def on_cache_hit(self, key: str, latency: float) -> None:
        """
        Chamado quando ocorre cache hit.
        
        Args:
            key: Chave do cache
            latency: Latência da operação em segundos
        """
        ...
    
    def on_cache_miss(self, key: str, latency: float) -> None:
        """
        Chamado quando ocorre cache miss.
        
        Args:
            key: Chave do cache
            latency: Latência da operação em segundos
        """
        ...
    
    def on_cache_write(self, key: str, size: int) -> None:
        """
        Chamado quando dados são escritos no cache.
        
        Args:
            key: Chave do cache
            size: Tamanho dos dados em bytes
        """
        ...
    
    def on_cache_error(self, key: str, error: Exception) -> None:
        """
        Chamado quando ocorre erro em operação de cache.
        
        Args:
            key: Chave do cache
            error: Exceção que ocorreu
        """
        ...
```

**Nota**: Esta é a estrutura básica do Protocol. Detalhes de implementação e métodos adicionais serão definidos durante a implementação da biblioteca.

## 10. Backends de Armazenamento

### 10.1 Backend de Armazenamento

O backend de armazenamento é sempre um **Dapr State Store**. A biblioteca não suporta backends customizados, focando exclusivamente na integração com Dapr.

**Interface interna do backend**:

- **get(key)**: Recupera dados serializados do Dapr State Store
- **set(key, value, ttl)**: Armazena dados com TTL no Dapr State Store
- **invalidate(key)**: Remove chave específica
- **invalidate_prefix(prefix)**: Remove chaves por prefixo (best-effort, depende do state store)

### 10.2 Implementação Dapr State Store

- **Cliente Dapr**: Usa DaprClient para comunicação
- **Timeout**: Delegado ao [Dapr Resiliency](https://docs.dapr.io/operations/resiliency/) (configurado externamente)
- **TTL**: Suporte nativo via `ttlInSeconds` metadata
- **Thread Safety**: Operações executadas em thread pool
- **Fallback**: Graceful degradation em caso de falha
- **State Stores**: Requer state store com suporte a TTL (Redis, MongoDB, PostgreSQL, etc.)

### 10.3 Invalidação e Limpeza

- **Invalidação Individual**: Remove chave específica via Dapr State Store
- **Invalidação por Prefixo**: Remove chaves por prefixo (depende do state store subjacente)
- **Best-Effort**: Operações de invalidação não falham o fluxo da aplicação
- **Limpeza Automática**: TTL gerenciado nativamente pelo state store via `ttlInSeconds` ([ver documentação](https://docs.dapr.io/developing-applications/building-blocks/state-management/state-store-ttl/))
- **Responsabilidade**: Biblioteca delega invalidação ao Dapr - comportamento específico varia por state store
- **Para Testes**: Use Dapr State Store Memory component

**Comportamento Best-Effort para Invalidação por Prefixo**:

- A operação tenta invalidar via Dapr State Store API
- Se state store não suporta invalidação por prefixo: Log de erro (nível ERROR) + operação falha gracefully
- Erro é notificado via hook `on_cache_error` (quando configurado)
- Exceção não é propagada - aplicação continua normalmente
- Recomendação: Use invalidação individual quando possível para garantir consistência

#### 10.3.1 Métodos de Invalidação

A biblioteca fornece métodos de invalidação tanto síncronos quanto assíncronos. Estes métodos são injetados no wrapper da função decorada:

**Disponibilidade dos Métodos**:

- Métodos são injetados como atributos do wrapper da função decorada
- Não estão disponíveis na função original antes da decoração
- Podem ser chamados diretamente através da função decorada

**Métodos Assíncronos**:

- `.invalidate(*args, **kwargs)` - Invalida chave específica
- `.invalidate_prefix(prefix)` - Invalida chaves por prefixo

**Métodos Síncronos**:

- `.invalidate_sync(*args, **kwargs)` - Versão síncrona da invalidação individual
- `.invalidate_prefix_sync(prefix)` - Versão síncrona da invalidação por prefixo

**Assinatura e Comportamento**:

- `.invalidate(*args, **kwargs)` recebe os mesmos argumentos da função decorada
- Reconstrói a chave de cache usando o mesmo algoritmo de geração de chave
- Invalida a entrada correspondente no Dapr State Store
- Best-effort: Erros são logados mas não propagados

**Exemplo de Uso**:

```python
# Função decorada
@cacheable(store_name="users")
async def get_user_profile(user_id: int) -> dict:
    return await fetch_user_data(user_id)  # função fictícia para exemplo

# Assíncrono: invalidar cache para user_id=123
await get_user_profile.invalidate(123)

# Síncrono: invalidar cache para user_id=456 (usa bridge interno)
get_user_profile.invalidate_sync(456)

# Invalidar por prefixo
await get_user_profile.invalidate_prefix("cache:get_user_profile")
```

## 11. Compatibilidade e Extensibilidade

### 11.1 Suporte a Sync/Async

- **Detecção Automática**: `inspect.iscoroutinefunction` para detectar async
- **Wrappers Específicos**: Wrappers diferentes para sync e async
- **Thread Safety**: Funções síncronas executadas em `ThreadPoolExecutor` global
- **Event Loop**: Estratégia para bridge sync/async
- **Resiliência**: Timeout, retry e circuit breaker delegados ao [Dapr Resiliency](https://docs.dapr.io/operations/resiliency/) (configurado externamente)

**Estratégia de Event Loop**:

1. Tenta obter loop em execução via `asyncio.get_running_loop()`
2. Se loop existe: Usa `loop.run_in_executor()` com ThreadPoolExecutor para executar operações assíncronas em thread separada
3. Se loop não existe (RuntimeError): Usa `asyncio.run()` em thread separada com novo event loop
4. Garante que operações síncronas nunca bloqueiam event loop ativo

### 11.2 Configuração do ThreadPoolExecutor

- **Pool Global**: ThreadPoolExecutor compartilhado globalmente por processo
- **Configuração Padrão**: `min(32, (os.cpu_count() or 1) + 4)` workers (padrão Python)
- **Criação**: Lazy - pool é criado na primeira chamada de função síncrona
- **Thread Safety**: Operações de cache executadas em thread separada
- **Event Loop**: Cada thread executa em loop próprio quando necessário
- **Configuração pelo Usuário**: Não exposta - biblioteca gerencia pool automaticamente (configuração interna)

### 11.3 Descriptor Protocol para Métodos

- **Suporte Completo**: Métodos de instância, classe e estáticos
- **Binding**: Preserva contexto de instância/classe
- **Transparência**: Métodos funcionam como se não fossem decorados
- **Identidade**: Tratamento especial de `self`/`cls` nas chaves

#### 11.3.1 Implementação do Descriptor

O decorator implementa `__get__` para suportar métodos, mas **NÃO** usa `functools.partial`. Em vez disso:

1. **Para métodos de instância**: Retorna wrapper com `self`/`cls` bound via closure
2. **Para métodos estáticos**: Retorna wrapper sem binding
3. **Para funções standalone**: `__get__` não é chamado

**Comportamento Específico**:

- Métodos de instância: `self` é automaticamente removido dos argumentos para geração de chave
- Métodos de classe: `cls` é automaticamente removido dos argumentos para geração de chave
- Métodos estáticos: Não há binding especial, funcionam como funções normais
- Preserva assinatura original e metadados da função

**Compartilhamento de Cache entre Instâncias**:

- Como `self`/`cls` são excluídos da geração de chave, o cache é compartilhado entre todas as instâncias da mesma classe
- **Exemplo**: `user1.get_data(id=5)` e `user2.get_data(id=5)` compartilham a mesma entrada de cache
- **Consequência**: Método com mesmos argumentos retorna mesmo resultado cached, independente da instância
- **Se quiser cache por instância**: Incluir identificador único da instância como argumento do método

```python
class UserService:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
    
    @cacheable(store_name="users")
    def get_user(self, user_id: int, tenant_id: str) -> dict:
        # tenant_id como argumento garante cache separado por tenant
        return fetch_user(tenant_id, user_id)  # função fictícia para exemplo
    
    def get_user_cached(self, user_id: int):
        # Passa tenant_id para garantir cache por instância
        return self.get_user(user_id, self.tenant_id)
```

### 11.4 Protocols para Extensibilidade

- **KeyBuilder**: Protocol para construtores de chaves customizados
- **Serializer**: Protocol para serializers customizados
- **TTLPolicy**: Protocol para políticas de TTL customizadas (não implementado)

## 12. Decisões Arquiteturais

### 12.1 Escolha do Dapr State Store

- **Motivação**: Reutilização de infraestrutura existente
- **Benefícios**: Consistência, observabilidade, configuração centralizada
- **Desenvolvimento e Testes**: Usar Dapr State Store Memory component configurado externamente

### 12.2 Deduplicação Assíncrona

- **Motivação**: Evitar thundering herd em cenários de alta concorrência
- **Implementação**: Futures compartilhadas por chave
- **Benefícios**: Redução significativa de computações redundantes

### 12.3 Separação de Responsabilidades

A arquitetura simplificada separa responsabilidades em camadas para melhorar manutenibilidade, testabilidade e extensibilidade:

1. **CacheableDecorator**: Configuração e interface pública
   - Responsabilidade: Configurar parâmetros e aplicar decorator
   - Interface: API pública do decorator (10 parâmetros)
   - Baixo acoplamento: Delega operações para componentes especializados

2. **CacheOrchestrator**: Coordenação do fluxo de cache
   - Responsabilidade: Orquestrar hit/miss logic (sem refresh-ahead)
   - Interface: Métodos para lookup, compute, store
   - Alta coesão: Toda lógica de cache em um lugar

3. **SyncAsyncBridge**: Conversão entre contextos síncronos/assíncronos
   - Responsabilidade: Converter entre sync/async de forma transparente
   - Interface: Métodos unificados que funcionam em ambos contextos
   - Isolamento: Lógica de conversão separada do resto

4. **CacheService**: Facade para DaprStateBackend + serializer + key_builder + dapr_crypto
   - Responsabilidade: Abstrair operações de cache
   - Interface: Métodos unificados para get/set/invalidate
   - Extensibilidade: Fácil troca de serializers e key builders

**Benefícios da Arquitetura Simplificada**:

- **Alta Coesão**: Cada componente tem responsabilidade única e bem definida
- **Baixo Acoplamento**: Componentes se comunicam via interfaces bem definidas
- **Testabilidade**: Componentes testáveis isoladamente com mocks
- **Manutenibilidade**: Mudanças localizadas, fácil de entender e modificar
- **Simplicidade**: Menos componentes, menos complexidade, mais foco no Dapr

## 13. Limitações e Considerações

### 13.1 Limitações Conhecidas

- **State Store TTL**: Requer state store com suporte a TTL ([ver lista](https://docs.dapr.io/reference/components-reference/supported-state-stores/))
- **Invalidação por Prefixo**: Best-effort, depende do state store subjacente
- **Serialização**: Tipos não serializáveis sem serializador customizado lançam `TypeError`
- **Dapr Dependency**: Biblioteca requer Dapr disponível e configurado corretamente
- **TTL Mínimo**: TTL deve ser >= 1 segundo (TTL=0 ou negativo inválido)
- **Cache Permanente**: Não suportado - sempre requer TTL configurado

### 13.2 Considerações de Performance

- **Overhead**: Decorator adiciona latência mínima
- **Serialização**: Pode ser custosa para objetos grandes
- **Deduplicação**: Overhead mínimo de gerenciamento de futures
- **TTL Nativo**: TTL gerenciado pelo state store (sem overhead adicional)
- **Dapr Cryptography**: Overhead mínimo usando building block nativo

### 13.3 Considerações de Segurança

- **Dados Sensíveis**: Use `use_dapr_crypto=True` para dados sensíveis (PII, tokens, etc.)
- **Criptografia**: Integração nativa com Dapr Cryptography building block
- **TTL**: Configuração adequada de TTL para dados sensíveis
- **Invalidação**: Necessidade de invalidação explícita para dados sensíveis
- **Backend**: Segurança depende da configuração do state store
- **Key Management**: Gerenciado pelo Dapr e componentes KMS configurados
- **Exemplo de Uso**:

```python
@cacheable(
    store_name="user-cache",
    use_dapr_crypto=True,
    crypto_component_name="user-data-kms",
    ttl_seconds=300  # TTL curto para dados sensíveis
)
async def get_user_pii(user_id: int) -> dict:
    return await fetch_user_sensitive_data(user_id)  # função fictícia para exemplo
```

## 14. Roadmap e Extensões Futuras

### 14.1 Melhorias Planejadas

- **Compressão**: Compressão automática de dados grandes
- **Clustering**: Suporte a cache distribuído via Dapr Actor
- **Metrics**: Integração com sistemas de métricas (Prometheus, etc.)
- **TTLPolicy**: Políticas adaptativas de TTL baseadas em padrões de uso
- **Cache Warming**: Pré-carregamento de cache
- **Cache Invalidation**: Invalidação baseada em eventos
- **Cache Analytics**: Análise avançada de padrões de uso

### 14.2 Extensões Possíveis

- **Cache Partitioning**: Particionamento por critérios
- **Advanced TTL Policies**: Políticas baseadas em uso, frequência, etc.
- **Multi-Tenant Cache**: Isolamento de cache por tenant
- **Cache Federation**: Integração com múltiplos Dapr clusters

## 15. Glossário

### 15.1 Termos Técnicos

- **Cache Hit**: Quando dados solicitados estão presentes no cache
- **Cache Miss**: Quando dados solicitados não estão no cache, requerendo computação
- **Hard TTL**: Expiração automática gerenciada pelo state store via `ttlInSeconds`
- **Read-Through**: Cache miss executa função e armazena resultado
- **Write-Through**: Escritas vão para cache e backend simultaneamente
- **Thundering Herd**: Múltiplas chamadas simultâneas para mesma chave causando computações redundantes
- **Best-Effort**: Operações que não falham o fluxo principal em caso de erro
- **Deduplicação**: Evitar execuções redundantes de operações concorrentes
- **Cross-Layer**: Compartilhamento de cache entre diferentes camadas da aplicação
- **Dapr State Store**: Backend de armazenamento do Dapr com suporte a TTL
- **Dapr Cryptography**: Building block do Dapr para operações de criptografia

### 15.2 Padrões Arquiteturais

- **Decorator Pattern**: Transparência no uso do cache sem modificar a função original
- **Strategy Pattern**: Intercambiabilidade de algoritmos (serializers, key builders)
- **Observer Pattern**: Sistema de hooks para observabilidade
- **Protocol Pattern**: Interfaces para extensibilidade e type safety
- **Facade Pattern**: CacheService abstrai DaprStateBackend + serializer + key_builder + dapr_crypto

## 16. Matriz de Compatibilidade e Validação

### 16.1 Compatibilidade de Versões

| Componente       | Versão Mínima | Versão Recomendada | Notas                                      |
|------------------|---------------|--------------------|--------------------------------------------|
| Python           | 3.12+         | 3.13+              | Requer type hints modernos                 |
| Dapr             | 1.11+         | 1.12+              | Suporte a Cryptography building block      |
| Dapr Python SDK  | 1.10+         | 1.11+              | Compatibilidade com Cryptography API       |

### 16.2 State Stores Compatíveis com TTL

| State Store  | Suporte TTL | Configuração   | Notas                             |
|--------------|-------------|----------------|-----------------------------------|
| Redis        | ✅ Nativo   | `ttlInSeconds` | Recomendado para produção         |
| MongoDB      | ✅ Nativo   | `ttlInSeconds` | Suporte via TTL index             |
| PostgreSQL   | ✅ Nativo   | `ttlInSeconds` | Via timestamp                     |
| Cosmos DB    | ✅ Nativo   | `ttlInSeconds` | Suporte nativo                    |
| Memory       | ✅ Nativo   | `ttlInSeconds` | Apenas para testes/dev            |
| SQL Server   | ❌ Limitado | Manual         | Requer implementação customizada  |
| Cassandra    | ❌ Limitado | Manual         | Requer implementação customizada  |

### 16.3 Dependências Opcionais

| Dependência     | Uso                 | Instalação              | Notas                              |
|-----------------|---------------------|-------------------------|------------------------------------|
| `msgpack`       | MsgpackSerializer   | `pip install msgpack`   | Serialização binária compacta      |
| `cryptography`  | Dapr Cryptography   | Incluído no Dapr        | Para operações de criptografia     |

### 16.4 Validações de Parâmetros

| Parâmetro                 | Validação          | Erro         | Ação                                     |
|---------------------------|--------------------|--------------|------------------------------------------|
| `ttl_seconds`             | `int >= 1` ou `None` | `ValueError` | TTL deve ser >= 1 segundo ou None (default 3600) |
| `key_prefix`              | `str` não vazio    | `ValueError` | Prefixo não pode ser vazio               |
| `store_name`              | `str` não vazio    | `ValueError` | Nome do store não pode ser vazio         |

### 16.5 Combinações Inválidas

| Combinação                                     | Problema               | Solução                                              |
|------------------------------------------------|------------------------|------------------------------------------------------|
| `ttl_seconds=0` ou `ttl_seconds < 1`           | TTL inválido           | Use `ttl_seconds >= 1` ou `ttl_seconds=None` (default 3600) |
| `use_dapr_crypto=True` sem componente configurado | Log de erro + bypass criptografia | Configure componente de criptografia no Dapr ou remova flag |
| State store sem suporte a TTL                  | TTL não aplicado       | Use state store compatível (Redis, MongoDB, PostgreSQL, etc.) |

---

*Este documento representa a especificação técnica completa da biblioteca dapr-state-cache, capturando todas as regras, políticas e decisões arquiteturais implementadas no código.*
