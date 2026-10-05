# LangChain LLM client

The application and question-semantics CLI use `LangChainClient` with
`langchain-aws`'s `ChatBedrockConverse`. LiteLLM is no longer a dependency.
The existing LangGraph node contracts and response models remain the workflow
boundary; raw completions now return LangChain `AIMessage` objects.

## Bedrock configuration

Set these in the environment or the repository's `.env`:

```dotenv
GRAPH_RAG_LLM_MODEL=your-bedrock-model-or-inference-profile-id
GRAPH_RAG_LLM_REGION=us-east-1
# Optional named profile; omit when using an IAM role or other AWS credentials.
# GRAPH_RAG_LLM_AWS_PROFILE=work
```

The provider defaults to `bedrock_converse`; `bedrock` also selects Converse.
Use a native Bedrock model ID, inference-profile ID or ARN. A matching legacy
`bedrock_converse/` or `bedrock/` selector prefix is removed before invocation.
AWS credential and region discovery use the normal SDK chain, including workload
roles. `GRAPH_RAG_LLM_URL` is an optional Bedrock endpoint override and
`GRAPH_RAG_LLM_API_KEY` is an optional **Bedrock** API key. Old gateway URLs or keys
must be replaced with Bedrock configuration.

Temperature and maximum tokens retain their existing settings. The timeout now
sets SDK connection and read timeouts, rather than an overall request deadline.
SDK retries default to zero; LangGraph retries transient connection, timeout,
throttling and server errors. Authentication and request-validation errors are
not retried. Increasing SDK retries also multiplies attempts inside each graph
attempt.

To use another LangChain integration, inject a configured `BaseChatModel` into
`LangChainClient(settings, chat_model=model)` or
`GraphRagNodeRunner(settings, chat_model=model)`. The default factory creates only
a Bedrock client. Native `BaseTool` objects, JSON tool definitions and Pydantic
model classes can be passed to `complete(tools=...)`.

## Forced structured responses

`LangChainStructuredOutput` binds one synthetic `StructuredTool` named
`return_structured_output`, forces that name, then validates the returned
arguments with the requested Pydantic model. The output tool describes a response
and is never executed. Its JSON schema preserves the original model's field
constraints and extra-field rules; passing the class through the current
`StructuredTool` conversion would lose the top-level extra-field rule.

The adapter rejects missing, multiple, wrong-name, malformed and schema-invalid
tool calls. Bedrock has no generic `parallel_tool_calls` parameter; the client
rejects multiple returned calls when that option is false. A Bedrock model must
support named forced tool choice. Configurations whose advertised capabilities
would cause LangChain to downgrade forced choice to `auto` are rejected before
invocation. Provider-side strict schema generation is not assumed; local
validation remains authoritative.

Tests exercise the installed LangChain/core and AWS integrations, including
native Converse request serialization and response parsing, with AWS calls
stubbed. They do not establish account access, regional model availability or
live model compliance. A live smoke test requires your configured AWS account
and a model supporting forced tool choice.

API references:
[LangChain Bedrock integration](https://docs.langchain.com/oss/python/integrations/chat/bedrock),
[AWS credential discovery](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html).
