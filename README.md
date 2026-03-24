# AWS Python Framework

Mini-framework to create REST APIs, SQS Consumers, SNS Publishers, Fargate Tasks, and Standalone Lambdas with Python in AWS Lambda.

## 🚀 Features

- **Reusable single handler**: A single handler for all your API routes
- **Dynamic controller loading**: Routing based on convention
- **OOP structure**: Object-oriented programming for your code
- **Flexible MongoDB**: Direct access to multiple databases without models
- **External MongoDB**: Connect to multiple MongoDB clusters simultaneously
- **Multi-state routing**: Automatic `constitution-state` propagation across the entire call chain for per-state database routing
- **SQS Consumers**: Same pattern to process SQS messages (single or batch mode)
- **SNS Publishers**: Same pattern to publish messages to SNS topics
- **Fargate Tasks**: Same pattern to run tasks in Fargate containers
- **Standalone Lambdas**: Create lambdas invocable directly with AWS SDK
- **Authentication middleware**: Built-in token-based authentication
- **JSON utilities**: Automatic serialization of MongoDB types
- **Type hints**: Modern Python with type annotations
- **Async/await**: Full support for asynchronous operations

## 🔧 Installation

```bash
pip install aws-python-helper
```

## 📦 Quick Reference

All available classes and functions:

| Class / Function | Import | Purpose |
|------------------|--------|---------|
| `API` | `aws_python_helper.api.base` | Base class for REST endpoints |
| `api_handler` | `aws_python_helper.api.handler` | Generic handler for API Gateway |
| `SQSConsumer` | `aws_python_helper.sqs.consumer_base` | Base class for SQS consumers |
| `sqs_handler` | `aws_python_helper.sqs.handler` | Factory handler for SQS |
| `SNSPublisher` | `aws_python_helper.sns.publisher` | Base class for SNS publishers |
| `Lambda` | `aws_python_helper.lambda_standalone.base` | Base class for Standalone Lambdas |
| `lambda_handler` | `aws_python_helper.lambda_standalone.handler` | Factory handler for Lambda |
| `FargateTask` | `aws_python_helper.fargate.task_base` | Base class for Fargate tasks |
| `FargateExecutor` | `aws_python_helper.fargate.executor` | Launches Fargate tasks from Lambda |
| `fargate_handler` | `aws_python_helper.fargate.handler` | Entry point handler for Fargate |
| `Repository` | `aws_python_helper.repository.base` | Base class for MongoDB repositories |
| `get_state` | `aws_python_helper` | Read the current constitution-state from async context |
| `set_state` | `aws_python_helper` | Set the current constitution-state in async context |
| `MongoJSONEncoder` | `aws_python_helper.utils.json_encoder` | JSON encoder for MongoDB types |
| `mongo_json_dumps` | `aws_python_helper.utils.json_encoder` | Helper to serialize MongoDB types |
| `serialize_mongo_types` | `aws_python_helper.utils.serializer` | Recursively serialize MongoDB types |
| `UnauthorizedError` | `aws_python_helper.api.exceptions` | 401 authentication exception |
| `ForbiddenError` | `aws_python_helper.api.exceptions` | 403 authorization exception |

## 📂 Project Structure

This framework follows a convention-based folder structure. Here's the recommended organization:

```
your-project/
└── src/
    ├── api/                           # REST APIs
    │   └── users/                     # Resource folder (kebab-case)
    │       ├── get.py                 # GET /users/123 -> UserGetAPI
    │       ├── list.py                # GET /users -> UserListAPI
    │       ├── post.py                # POST /users -> UserPostAPI
    │       ├── put.py                 # PUT /users/123 -> UserPutAPI
    │       └── delete.py              # DELETE /users/123 -> UserDeleteAPI
    │
    ├── consumer/                     # SQS Consumers (direct files)
    │   ├── user_created.py            # user-created -> UserCreatedConsumer
    │   ├── title_indexed.py           # title-indexed -> TitleIndexedConsumer
    │   └── order_processed.py         # order-processed -> OrderProcessedConsumer
    │
    ├── lambda/                        # Standalone Lambdas (folders)
    │   ├── generate-route/            # generate-route -> GenerateRouteLambda
    │   │   └── main.py
    │   ├── sync-carrier/              # sync-carrier -> SyncCarrierLambda
    │   │   └── main.py
    │   └── process-payment/           # process-payment -> ProcessPaymentLambda
    │       └── main.py
    │
    ├── task/                         # Fargate Tasks (folders)
    │   ├── search-tax-by-town/        # search-tax-by-town -> SearchTaxByTownTask
    │   │   ├── main.py                # Entry point
    │   │   └── task.py                # Task class
    │   └── process-data/              # process-data -> ProcessDataTask
    │       ├── main.py
    │       └── task.py
    │
    └── topic/                        # SNS Publishers
        └── order_created.py           # OrderCreatedTopic
```

### Naming Conventions

The framework uses automatic class name detection based on your folder/file structure:

| Type | Handler Name | File Path | Class Name |
|------|--------------|-----------|------------|
| **API** | N/A | `src/api/users/list.py` | `UsersListAPI` |
| **Consumer** | `user-created` | `src/consumer/user_created.py` | `UserCreatedConsumer` |
| **Lambda** | `generate-route` | `src/lambda/generate-route/main.py` | `GenerateRouteLambda` |
| **Task** | `search-tax-by-town` | `src/task/search-tax-by-town/task.py` | `SearchTaxByTownTask` |

**Rules:**
- Handler names use **kebab-case** (e.g., `user-created`, `generate-route`)
- Consumer files use **snake_case** (e.g., `user_created.py`)
- Lambda folders use **kebab-case** (e.g., `generate-route/`)
- Task folders use **kebab-case** (e.g., `search-tax-by-town/`)
- Class names always use **PascalCase** with suffix (e.g., `UserCreatedConsumer`)

## 📝 Basic Usage

### Create an Endpoint

**1. Create your API class** in `src/api/constitutions/list.py`:

```python
from aws_python_helper.api.base import API

class ConstitutionListAPI(API):
    async def process(self):
        # Direct access to MongoDB
        constitutions = await self.db.constitution_db.constitutions.find().to_list(100)
        self.set_body(constitutions)
```

**2. The routing is automatic:**
- `GET /constitutions` → `src/api/constitutions/list.py`
- `GET /constitutions/123` → `src/api/constitutions/get.py`
- `POST /constitutions` → `src/api/constitutions/post.py`

**3. Configure the generic handler** (`src/handlers/api_handler.py`):

```python
from aws_python_helper.api.handler import api_handler
handler = api_handler
```

### Create an SQS Consumer

**1. Create your consumer** in `src/consumer/title_indexed.py`:

```python
from aws_python_helper.sqs.consumer_base import SQSConsumer

class TitleIndexedConsumer(SQSConsumer):
    async def process_record(self, record):
        body = self.extract_content_message(record)
        # Your logic here
        await self.db.constitution_db.titles.insert_one(body)
```

**2. Configure the handler** in `src/handlers/sqs_handler.py`:

```python
from aws_python_helper.sqs.handler import sqs_handler

# Create a handler for each consumer and export it
title_indexed_handler = sqs_handler('title-indexed')

__all__ = ['title_indexed_handler']
```

### Create a Standalone Lambda

Standalone lambdas are functions that can be invoked directly using the AWS SDK, without an HTTP endpoint. They're perfect for internal operations, integrations, and background processing tasks.

**Differences with APIs:**
- No API Gateway - invoked directly with AWS SDK
- No HTTP methods or routing
- Can be called from other lambdas, Step Functions, or any AWS service
- Perfect for internal microservices communication

**1. Create your lambda class** in `src/lambda/generate-route/main.py`:

```python
from aws_python_helper.lambda_standalone.base import Lambda
from datetime import datetime

class GenerateRouteLambda(Lambda):
    async def validate(self):
        # Validate input data
        if 'shipping_id' not in self.data:
            raise ValueError("shipping_id is required")

        if not isinstance(self.data['shipping_id'], str):
            raise TypeError("shipping_id must be a string")

    async def process(self):
        # Your business logic here
        shipping_id = self.data['shipping_id']

        # Access to MongoDB
        shipping = await self.db.deliveries.shippings.find_one(
            {'_id': shipping_id}
        )

        if not shipping:
            raise ValueError(f"Shipping {shipping_id} not found")

        # Create route
        route = {
            'shipping_id': shipping_id,
            'carrier_id': shipping.get('carrier_id'),
            'status': 'pending',
            'created_at': datetime.utcnow()
        }

        result = await self.db.deliveries.routes.insert_one(route)

        self.logger.info(f"Route created: {result.inserted_id}")

        # Return result
        return {
            'route_id': str(result.inserted_id),
            'shipping_id': shipping_id
        }
```

**2. Configure the handler** in `src/handlers/lambda_handler.py`:

```python
from aws_python_helper.lambda_standalone.handler import lambda_handler

# Create a handler for each lambda and export it
generate_route_handler = lambda_handler('generate-route')
sync_carrier_handler = lambda_handler('sync-carrier')
process_payment_handler = lambda_handler('process-payment')

__all__ = [
    'generate_route_handler',
    'sync_carrier_handler',
    'process_payment_handler'
]
```

**Note:** The handler name `'generate-route'` (kebab-case) will automatically look for:
- Folder: `src/lambda/generate-route/` (kebab-case)
- File: `main.py`
- Class: `GenerateRouteLambda`

**3. Invoke from another Lambda or API** using boto3:

```python
import boto3
import json

lambda_client = boto3.client('lambda')

# Invoke synchronously (RequestResponse)
response = lambda_client.invoke(
    FunctionName='GenerateRouteLambda',
    InvocationType='RequestResponse',
    Payload=json.dumps({
        'constitution-state': 'connecticut',  # Required
        'data': {
            'shipping_id': '507f1f77bcf86cd799439011'
        }
    })
)

result = json.loads(response['Payload'].read())
# {'success': True, 'data': {'route_id': '...', 'shipping_id': '...'}}

if result['success']:
    print(f"Route created: {result['data']['route_id']}")
else:
    print(f"Error: {result['error']}")
```

**4. Invoke asynchronously** (fire and forget):

```python
# Invoke asynchronously (Event)
lambda_client.invoke(
    FunctionName='GenerateRouteLambda',
    InvocationType='Event',  # Asynchronous
    Payload=json.dumps({
        'constitution-state': 'connecticut',  # Required
        'data': {
            'shipping_id': '507f1f77bcf86cd799439011'
        }
    })
)
# Returns immediately without waiting for the result
```

**Naming Convention:**

| Lambda Name (kebab-case) | Folder | File | Class |
|--------------------------|--------|------|-------|
| `generate-route` | `src/lambda/generate-route/` | `main.py` | `GenerateRouteLambda` |
| `sync-carrier` | `src/lambda/sync-carrier/` | `main.py` | `SyncCarrierLambda` |
| `process-payment` | `src/lambda/process-payment/` | `main.py` | `ProcessPaymentLambda` |
| `send-notification` | `src/lambda/send-notification/` | `main.py` | `SendNotificationLambda` |

**Common Use Cases:**
- Internal microservices communication
- Background data processing
- Integration with external services
- Scheduled tasks (with EventBridge)
- Step Functions workflows
- Cross-service operations

### Publish to SNS

**1. Create your topic** in `src/topic/title_indexed.py`:

```python
from aws_python_helper.sns.publisher import SNSPublisher
import os

class TitleIndexedTopic(SNSPublisher):
    def __init__(self):
        super().__init__(
            topic_arn=os.getenv('TITLE_INDEXED_SNS_TOPIC_ARN')
        )

    def build_message(self, constitution_id, title, event_type='title_indexed'):
        return {
            'content': {
                'constitution_id': constitution_id,
                'title': title,
                'event_type': event_type
            },
            'attributes': {
                'event_type': event_type   # Used for SNS subscription filtering
            }
        }
```

**2. Use the topic** from anywhere:

```python
from src.topic.title_indexed import TitleIndexedTopic

# In a consumer, API or task
topic = TitleIndexedTopic()

# Publish a single message
await topic.publish(topic.build_message('123', 'My Constitution'))

# Publish multiple messages in batch
messages = [
    topic.build_message('id1', 'Constitution A'),
    topic.build_message('id2', 'Constitution B'),
]
await topic.publish(messages)
```

**Message format** — every message must have a `content` key:

```python
{
    'content': {...},              # Required: message body (any dict)
    'attributes': {...},           # Optional: SNS message attributes for filtering
    'subject': 'Optional subject'  # Optional: message subject
}
```

### Run a Fargate Task

**1. Create your task** in `src/task/search-tax-by-town/task.py`:

```python
from aws_python_helper.fargate.task_base import FargateTask

class SearchTaxByTownTask(FargateTask):

    async def execute(self):
        town = self.require_env('TOWN')
        self.logger.info(f"Processing town: {town}")

        # Access to DB
        docs = await self.db.smart_data.address.find({'town': town}).to_list()

        # Your logic here
        for doc in docs:
            # Process document
            pass
```

**2. Create the entry point** in `src/task/search-tax-by-town/main.py`:

```python
from aws_python_helper.fargate.handler import fargate_handler
import sys

if __name__ == '__main__':
    exit_code = fargate_handler('search-tax-by-town')
    sys.exit(exit_code)
```

**3. Create the Dockerfile** in `src/task/search-tax-by-town/Dockerfile`:

```dockerfile
FROM python:3.10.12-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/framework_requirements.txt
COPY src/task/search-tax-by-town/requirements.txt /app/task_requirements.txt
RUN pip install -r /app/framework_requirements.txt && \
    pip install -r /app/task_requirements.txt

# Copy code
COPY aws_python_helper /app/aws_python_helper
COPY config.py /app/config.py
COPY task /app/task
COPY task/search-tax-by-town/main.py /app/main.py

ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
```

**4. Invoke from Lambda**:

```python
from aws_python_helper.fargate.executor import FargateExecutor

def handler(event, context):
    executor = FargateExecutor()
    # constitution-state is auto-propagated as CONSTITUTION_STATE env var in the container
    task_arn = executor.run_task(
        'search-tax-by-town',
        envs={'TOWN': 'Norwalk', 'ONLY_TAX': 'true'}
    )
    return {'taskArn': task_arn}
```

## 🗄️ Access to MongoDB

The framework provides flexible access to multiple databases:

```python
class MyAPI(API):
    async def process(self):
        # Access to different databases on the same cluster
        user = await self.db.users_db.users.find_one({'_id': user_id})

        # Another database
        await self.db.analytics_db.logs.insert_one({'action': 'view'})

        # Multiple collections
        titles = await self.db.constitution_db.titles.find().to_list(100)
        articles = await self.db.constitution_db.articles.find().to_list(100)
```

The pattern is always: `self.db.<database_name>.<collection_name>.<motor_operation>()`

### External MongoDB Clusters

Connect to additional MongoDB clusters using `EXTERNAL_MONGODB_CONNECTIONS`:

```bash
EXTERNAL_MONGODB_CONNECTIONS='[
    {"name": "ClusterDockets", "connection_string": "mongodb+srv://cluster.mongodb.net"},
    {"name": "ClusterAnalytics", "connection_string": "mongodb+srv://analytics.mongodb.net"}
]'
```

The credentials from `MONGO_DB_USER` / `MONGO_DB_PASSWORD` are automatically injected into the connection strings.

Access external clusters via `self.external_db`:

```python
class AddressAPI(API):
    async def process(self):
        # Access external cluster: self.external_db.<ClusterName>.<database>.<collection>
        addresses = await self.external_db.ClusterDockets.smart_data.addresses.find(
            {'town': self.data['town']}
        ).to_list(100)

        self.set_body({'addresses': addresses})
```

`self.external_db` is available in `API`, `SQSConsumer`, `Lambda`, and `FargateTask`.

## 🗂️ Repository Pattern

The framework provides a `Repository` base class that eliminates repetitive boilerplate in data access layers. Each repository only declares what collection it uses, whether it belongs to an external cluster, and what indexes to create. The base class handles the MongoDB connection and index creation automatically.

### Properties to override

| Property | Type | Default | Required |
|----------|------|---------|----------|
| `collection_name` | `str` | — | **Yes** |
| `database_key` | `str \| None` | `None` | No — if `None`, uses `constitution-state` from context |
| `is_external` | `bool` | `False` | No |
| `cluster_name` | `str` | `None` | Only if `is_external=True` |
| `indexes` | `list` | `[]` | No |

**`database_key` controls how the database is resolved:**
- `database_key = "core"` (or any string) → always connects to that specific database.
- `database_key = None` (default) → reads `constitution-state` from the async context automatically. This makes the repository **state-scoped**: it connects to `"connecticut"`, `"new_jersey"`, etc. depending on the current request.

Collections are cached per `(database_name, collection_name)` key — state-scoped repositories correctly isolate state between concurrent requests.

### Index format

```python
@property
def indexes(self):
    return [
        {"key": [("field", 1)]},                               # simple ASC
        {"key": [("field", -1)]},                              # simple DESC
        {"key": [("f1", 1), ("f2", -1)], "unique": True},     # compound + unique
        {"key": [("expires_at", 1)], "expireAfterSeconds": 0}, # TTL index
    ]
```

Indexes are created automatically in the background on first collection access — no need to call any initialization method.

### Repository with a fixed database

```python
from aws_python_helper import Repository

class TownsRepository(Repository):

    @property
    def collection_name(self):
        return "towns"

    @property
    def database_key(self):
        return "core"  # always connects to the "core" database

    @property
    def indexes(self):
        return [
            {"key": [("name", 1)]},
            {"key": [("platform", 1)]},
        ]

    async def get_available(self, platforms):
        return await self.collection.find(
            {"platform": {"$in": platforms}},
            {"name": 1, "platform": 1}
        ).to_list(length=None)

    async def find_by_name(self, name):
        return await self.collection.find_one({"name": name})
```

### State-scoped repository (no `database_key`)

When `database_key` is not set, the repository reads the current `constitution-state` from context and uses it as the database name. The same repository instance connects to `"connecticut"` for one request and to `"new_jersey"` for another — automatically.

```python
from aws_python_helper import Repository

class LandRecordsRepository(Repository):

    @property
    def collection_name(self):
        return "records"

    # No database_key → uses get_state() automatically
    # If constitution-state = "connecticut" → connects to DB "connecticut"
    # If constitution-state = "new_jersey"  → connects to DB "new_jersey"

    @property
    def indexes(self):
        return [
            {"key": [("unique_id", 1)]},
            {"key": [("owner", 1), ("town", 1)]},
        ]

    async def bulk_upsert(self, records):
        from pymongo import UpdateOne
        operations = [
            UpdateOne({"unique_id": r["unique_id"]}, {"$set": r}, upsert=True)
            for r in records
        ]
        result = await self.collection.bulk_write(operations)
        return {"upserted": result.upserted_count, "modified": result.modified_count}
```

> **Note:** A `ValueError` is raised at runtime if `database_key` is `None` and `constitution-state` has not been set in the context. This is prevented automatically by the framework at every entry point (API, Lambda, SQS, Fargate).

### Repository on an external cluster

```python
from aws_python_helper import Repository

class AddressRepository(Repository):

    @property
    def database_key(self):
        return "smart_data"

    @property
    def collection_name(self):
        return "address"

    @property
    def is_external(self):
        return True

    @property
    def cluster_name(self):
        return "ClusterDockets"  # Must match a name in EXTERNAL_MONGODB_CONNECTIONS

    async def find_by_query(self, query, limit=None):
        cursor = self.collection.find(query)
        if limit:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=None)
```

### Instantiation — no `db` argument needed

```python
class MyAPI(API):

    @property
    def towns_repository(self):
        if not self._towns_repository:
            self._towns_repository = TownsRepository()  # no args!
        return self._towns_repository

    async def process(self):
        towns = await self.towns_repository.get_available(["platform_a", "platform_b"])
        self.set_body({"towns": towns})
```

The repository connects itself using the already-initialized `MongoManager` singleton — the same one used by `self.db`. No need to pass `self.db` or any connection object.

## 🌐 Constitution State

The framework uses a `constitution-state` value to support **multi-state database routing** — connecting each request to the correct database based on the state it belongs to (e.g., `"connecticut"`, `"new_jersey"`). This value is propagated automatically across the entire async call chain using Python's `contextvars.ContextVar`, so you never need to pass it manually between layers.

### How the framework injects it at each entry point

| Entry point | How `constitution-state` is read |
|-------------|----------------------------------|
| **API Gateway** | HTTP header `constitution-state` — **required**, returns `400` if missing |
| **Standalone Lambda** | Field `constitution-state` in the event payload — **required**, raises `ValueError` if missing |
| **SQS Consumer (single mode)** | Per-record: reads from SNS `MessageAttributes['constitution-state']`, falls back to `body.constitution_state` |
| **SQS Consumer (batch mode)** | Groups records by state; calls `process_batch()` once per group with the correct state in context |
| **Fargate Task** | Env var `CONSTITUTION_STATE` — auto-injected by `FargateExecutor` |

### How the framework propagates it to downstream services

| Downstream service | Propagation mechanism |
|--------------------|-----------------------|
| **SNS Publisher** | Auto-injects `constitution-state` as a `MessageAttribute` on every published message |
| **FargateExecutor** | Auto-injects `CONSTITUTION_STATE` as an env var when launching Fargate containers |

This means that an API call with `constitution-state: connecticut` will automatically carry that state through SNS → SQS → Fargate without any code changes in your consumers or tasks.

### State-scoped repositories

Repositories with no `database_key` (default) read `constitution-state` from context to resolve the target database automatically. See the [Repository Pattern](#️-repository-pattern) section for details.

### Manual access

If you need to read or set the state manually (e.g., in tests or utility code):

```python
from aws_python_helper import get_state, set_state

state = get_state()      # e.g. "connecticut", or None if not set
set_state("new_jersey")  # set manually (the framework does this automatically)
```

### API example — `constitution-state` header

```
GET /constitutions HTTP/1.1
constitution-state: connecticut
Authorization: Bearer <token>
```

### Lambda invocation example — `constitution-state` in event

```python
import boto3, json

lambda_client = boto3.client('lambda')
lambda_client.invoke(
    FunctionName='MyLambdaFunction',
    InvocationType='RequestResponse',
    Payload=json.dumps({
        'constitution-state': 'connecticut',   # Required
        'data': {'key': 'value'}
    })
)
```

## 🔄 Routing Convention

The framework uses convention over configuration for the routing:

| Request | Loaded file |
|---------|----------------|
| `GET /users` | `api/users/list.py` |
| `GET /users/123` | `api/users/get.py` |
| `POST /users` | `api/users/post.py` |
| `PUT /users/123` | `api/users/put.py` |
| `DELETE /users/123` | `api/users/delete.py` |
| `GET /users/123/posts` | `api/users/posts/list.py` |
| `GET /users/123/posts/456` | `api/users/posts/get.py` |

**Logic:**
- The parts with **even indices** (0,2,4...) are **directories**
- The parts with **odd indices** (1,3,5...) are **path parameters**
- `GET` with **odd number of parts** → **list** method
- `GET` with **even number of parts** → **get** method
- Other methods use their name directly

## 🧩 API Class Reference

All properties and methods available inside an `API` subclass:

### Request Properties

| Property | Type | Description |
|----------|------|-------------|
| `self.data` | `dict` | Request body (POST/PUT) or query params (GET) |
| `self.headers` | `dict` | HTTP request headers |
| `self.path_parameters` | `dict` | URL path parameters (e.g. `/users/123` → `{'id': '123'}`) |
| `self.query_parameters` | `dict` | Query string parameters |
| `self.db` | `DatabaseProxy` | Access to main MongoDB cluster |
| `self.external_db` | `ExternalDatabaseProxy` | Access to external MongoDB clusters |
| `self.current_user` | `dict \| None` | Authenticated user document (requires `REQUIRE_AUTH=true`) |
| `self.is_authenticated` | `bool` | Whether the request is authenticated |
| `self.auth_data` | `dict \| None` | Full authentication data |

### Response Methods

| Method | Description |
|--------|-------------|
| `self.set_code(code: int)` | Set HTTP response status code |
| `self.set_body(body: Any)` | Set response body (auto-serialized to JSON) |
| `self.set_header(key: str, value: str)` | Add a single response header |
| `self.set_headers(headers: dict)` | Set multiple response headers at once |

### Methods to Override

| Method | Required | Description |
|--------|----------|-------------|
| `async validate()` | Optional | Validate request data, raise exceptions to reject |
| `async process()` | **Required** | Main business logic |

```python
class UserGetAPI(API):
    async def validate(self):
        # Access path params: /users/123 → self.path_parameters = {'id': '123'}
        if not self.path_parameters.get('id'):
            raise ValueError("User ID is required")

    async def process(self):
        user_id = self.path_parameters['id']
        user = await self.db.users_db.users.find_one({'_id': user_id})

        if not user:
            self.set_code(404)
            self.set_body({'error': 'User not found'})
            return

        self.set_code(200)
        self.set_body({'data': user})
        self.set_header('X-Resource-Id', user_id)
```

## 🔐 Authentication

The framework includes a built-in token-based authentication middleware.

### Configuration

```bash
REQUIRE_AUTH=true            # Enable authentication (default: false)
AUTH_DB_NAME=my_database     # MongoDB database where tokens are stored
AUTH_BYPASS_TOKEN=secret123  # Master token to bypass auth (for internal use)
```

### Using the authenticated user

When `REQUIRE_AUTH=true`, every request must include a valid `Authorization: Bearer <token>` header. The authenticated user is available via `self.current_user`:

```python
class OrderListAPI(API):
    async def process(self):
        # self.current_user contains the user document from MongoDB
        user_id = self.current_user['_id']

        orders = await self.db.orders_db.orders.find(
            {'user_id': user_id}
        ).to_list(100)

        self.set_body({'data': orders})
```

### Auth exceptions

Use these exceptions in your `validate()` or `process()` methods:

```python
from aws_python_helper.api.exceptions import UnauthorizedError, ForbiddenError

class AdminOnlyAPI(API):
    async def validate(self):
        if not self.is_authenticated:
            raise UnauthorizedError("Authentication required")  # Returns 401

        if self.current_user.get('role') != 'admin':
            raise ForbiddenError("Admin access required")       # Returns 403
```

## 🎯 Complete Example

```python
# src/api/constitutions/list.py
from aws_python_helper.api.base import API

class ConstitutionListAPI(API):
    async def validate(self):
        if 'limit' in self.data:
            limit = int(self.data['limit'])
            if limit > 1000:
                raise ValueError("Limit cannot exceed 1000")

    async def process(self):
        # Build filters
        filters = {}
        if 'country' in self.data:
            filters['country'] = self.data['country']

        # Query MongoDB
        limit = int(self.data.get('limit', 100))
        results = await self.db.constitution_db.constitutions.find(
            filters
        ).limit(limit).to_list(limit)

        # Count total
        total = await self.db.constitution_db.constitutions.count_documents(filters)

        # Register in analytics
        await self.db.analytics_db.searches.insert_one({
            'filters': filters,
            'result_count': len(results)
        })

        # Response
        self.set_body({
            'data': results,
            'total': total
        })
        self.set_header('X-Total-Count', str(total))
```

## 🔗 Integration Example: API + Standalone Lambda

Here's a complete example showing how an API can invoke a standalone lambda:

**Scenario:** An API endpoint that creates a shipping and then asynchronously generates its route using a standalone lambda.

**1. The API endpoint** (`src/api/shippings/post.py`):

```python
from aws_python_helper.api.base import API
import boto3
import json

class ShippingPostAPI(API):
    async def validate(self):
        required_fields = ['customer_id', 'address', 'items']
        for field in required_fields:
            if field not in self.data:
                raise ValueError(f"{field} is required")

    async def process(self):
        # Create shipping in database
        shipping = {
            'customer_id': self.data['customer_id'],
            'address': self.data['address'],
            'items': self.data['items'],
            'status': 'pending',
            'route_pending': True
        }

        result = await self.db.deliveries.shippings.insert_one(shipping)
        shipping_id = str(result.inserted_id)

        # Invoke standalone lambda asynchronously to generate route
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName='GenerateRouteLambda',
            InvocationType='Event',  # Asynchronous
            Payload=json.dumps({
                'data': {'shipping_id': shipping_id}
            })
        )

        self.set_code(201)
        self.set_body({
            'shipping_id': shipping_id,
            'status': 'pending',
            'message': 'Shipping created, route generation in progress'
        })
```

**2. The standalone lambda** (`src/lambda/generate-route/main.py`):

```python
from aws_python_helper.lambda_standalone.base import Lambda

class GenerateRouteLambda(Lambda):
    async def validate(self):
        if 'shipping_id' not in self.data:
            raise ValueError("shipping_id is required")

    async def process(self):
        shipping_id = self.data['shipping_id']

        # Get shipping details
        shipping = await self.db.deliveries.shippings.find_one(
            {'_id': shipping_id}
        )

        if not shipping:
            raise ValueError(f"Shipping {shipping_id} not found")

        # Generate optimal route
        route = await self.calculate_optimal_route(shipping)

        # Save route
        route_result = await self.db.deliveries.routes.insert_one(route)

        # Update shipping
        await self.db.deliveries.shippings.update_one(
            {'_id': shipping_id},
            {'$set': {
                'route_id': route_result.inserted_id,
                'route_pending': False,
                'status': 'scheduled'
            }}
        )

        return {
            'route_id': str(route_result.inserted_id),
            'shipping_id': shipping_id
        }

    async def calculate_optimal_route(self, shipping):
        # Your route calculation logic here
        return {
            'shipping_id': shipping['_id'],
            'carrier_id': shipping.get('carrier_id'),
            'estimated_duration': 60,
            'status': 'pending'
        }
```

**3. Configure handlers** (`src/handlers/lambda_handler.py`):

```python
from aws_python_helper.lambda_standalone.handler import lambda_handler

generate_route_handler = lambda_handler('generate-route')

__all__ = ['generate_route_handler']
```

**Benefits of this pattern:**
- API responds immediately (better UX)
- Route generation happens in the background
- Decoupled services (easier to maintain)
- Can retry lambda independently if it fails
- Scalable architecture

## 🏗️ Architecture Overview

Typical flow for event-driven architectures using this framework:

```
┌──────────┐     ┌─────────────┐     ┌──────────────────────────────────────┐
│  Client  │────▶│ API Gateway │────▶│  Lambda: api_handler                 │
└──────────┘     └─────────────┘     │  (src/api/resource/post.py)          │
                                     │  → validates, queries MongoDB,        │
                                     │    publishes to SNS                   │
                                     └────────────────┬─────────────────────┘
                                                      │
                                                      ▼
                                             ┌─────────────────┐
                                             │   SNS Topic     │
                                             │ (fanout/filter) │
                                             └────────┬────────┘
                                      ┌───────────────┼───────────────┐
                                      ▼               ▼               ▼
                               ┌────────────┐  ┌────────────┐  ┌────────────┐
                               │  SQS Queue │  │  SQS Queue │  │  SQS Queue │
                               │  Platform A│  │  Platform B│  │  Platform C│
                               └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
                                     │               │               │
                                     ▼               ▼               ▼
                               ┌──────────────────────────────────────────────┐
                               │  Lambda: sqs_handler                         │
                               │  (src/consumer/platform_consumer.py)         │
                               │  → groups messages, acquires sessions,        │
                               │    launches Fargate tasks                     │
                               └───────────────────┬──────────────────────────┘
                                                   │  FargateExecutor.run_task()
                                                   ▼
                               ┌──────────────────────────────────────────────┐
                               │  Fargate Task: fargate_handler               │
                               │  (src/task/my-task/task.py)                  │
                               │  → scrapes/processes data,                   │
                               │    writes results to MongoDB                  │
                               └──────────────────────────────────────────────┘
```

## 🔐 Environment Variables

### MongoDB Configuration

The framework supports two ways to configure MongoDB:

#### Option 1: Full Connection String

```bash
# Full URI with embedded credentials
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/dbname?retryWrites=true&w=majority
# or
MONGO_DB_URI=mongodb+srv://user:password@cluster.mongodb.net/dbname
```

#### Option 2: Separate Components (Recommended for Terraform)

```bash
# Host without credentials
MONGO_DB_HOST=mongodb+srv://cluster.mongodb.net

# Credentials (more secure)
MONGO_DB_USER=admin
MONGO_DB_PASSWORD=my-secure-password

# Optional
MONGO_DB_NAME=my_database
MONGO_DB_OPTIONS=retryWrites=true&w=majority
```

**Benefits of separate components:**
- ✅ Better security: credentials separate from host
- ✅ Easy integration with Terraform/AWS Secrets Manager
- ✅ Passwords with special characters are handled automatically
- ✅ More flexible for different environments

The framework automatically:
1. URL-encodes the password (handles `@`, `:`, `/`, etc.)
2. Builds the full URI
3. Initializes the connection

#### Terraform Example

```hcl
environment_variables = {
  MONGO_DB_HOST     = module.mongodb.connection_string
  MONGO_DB_USER     = module.mongodb.database_user
  MONGO_DB_PASSWORD = module.mongodb.database_password
}
```

### All Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGODB_URI` or `MONGO_DB_URI` | One of these or components below | Full MongoDB connection string |
| `MONGO_DB_HOST` | Alt. to URI | MongoDB host (e.g. `mongodb+srv://cluster.net`) |
| `MONGO_DB_USER` | Alt. to URI | MongoDB username |
| `MONGO_DB_PASSWORD` | Alt. to URI | MongoDB password |
| `MONGO_DB_NAME` | Optional | Default database name |
| `MONGO_DB_OPTIONS` | Optional | Connection options (e.g. `retryWrites=true&w=majority`) |
| `EXTERNAL_MONGODB_CONNECTIONS` | Optional | JSON array of external cluster configurations |
| `REQUIRE_AUTH` | Optional | Enable authentication middleware (`true`/`false`) |
| `AUTH_DB_NAME` | If `REQUIRE_AUTH=true` | MongoDB database for token validation |
| `AUTH_BYPASS_TOKEN` | Optional | Master token to bypass authentication |
| `ECS_CLUSTER` | Fargate only | ECS cluster name for `FargateExecutor` |
| `ECS_SUBNETS` | Fargate only | Comma-separated subnet IDs for Fargate tasks |
| `CONSTITUTION_STATE` | Fargate only (auto) | State injected automatically by `FargateExecutor` — do not set manually |
| `AWS_REGION` | Fargate/SNS/SQS | AWS region |
| `AWS_ACCOUNT_ID` | SQS `get_queue_url` | AWS account ID |
| `SERVICE_NAME` | SQS `get_queue_url` | Service name prefix for queue name |
| `QUEUE_NAME` | SQS `get_queue_url` | Queue name segment |
| `ENV` | SQS `get_queue_url` | Environment suffix (e.g. `prod`, `dev`) |

## 📊 Advanced Features

### SQS Consumer - Batch Mode

By default, consumers process messages one by one (`"single"` mode). Use `"batch"` mode when you need to group or bulk-process messages.

**Constitution-state handling in SQS:**
- **Single mode**: the framework extracts `constitution-state` from each record automatically (from SNS `MessageAttributes`, then from `body.constitution_state`) and sets it in context before calling `process_record()`. You do not need to extract it yourself.
- **Batch mode**: the framework groups the incoming records by `constitution-state` and calls `process_batch()` once per group, with the correct state in context for each group. This ensures that state-scoped repositories resolve to the right database even when a batch contains records from different states.

```python
from aws_python_helper.sqs.consumer_base import SQSConsumer

class OrderConsumer(SQSConsumer):

    @property
    def processing_mode(self) -> str:
        return "batch"

    async def process_batch(self, records):
        # Group records by some key before processing
        grouped = {}
        for record in records:
            message_id = record.get('messageId')
            body = self.extract_content_message(record)
            key = body.get('region', 'default')
            grouped.setdefault(key, []).append((message_id, body))

        for region, messages in grouped.items():
            try:
                # Bulk operation for the whole group
                docs = [msg[1] for msg in messages]
                await self.db.orders_db.orders.insert_many(docs)
            except Exception as e:
                # Mark individual messages as failed
                for message_id, _ in messages:
                    self.add_message_failed(message_id, str(e))
```

**Key methods in SQSConsumer:**

| Method / Property | Description |
|-------------------|-------------|
| `self.extract_content_message(record)` | Parse message body (handles SNS → SQS wrapping automatically) |
| `self.parse_body(record)` | Alias for `extract_content_message` |
| `self.add_message_failed(message_id, error)` | Mark a message for retry (batch mode) |
| `self.get_queue_url()` | Get the SQS queue URL (uses `AWS_REGION`, `AWS_ACCOUNT_ID`, `SERVICE_NAME`, `QUEUE_NAME`, `ENV`) |
| `self.db` | Access to main MongoDB cluster |
| `self.external_db` | Access to external MongoDB clusters |

**Retry behavior:**
- Messages marked with `add_message_failed()` are reported via `reportBatchItemFailures`
- AWS SQS retries **only** the failed messages, not the whole batch
- Successful messages in the same batch are not retried

### SNS Publisher - Batch Publishing

The `SNSPublisher` automatically injects the current `constitution-state` as a `MessageAttribute` on every published message. SQS consumers built with this framework will then extract it automatically, ensuring the state flows end-to-end through the SNS → SQS chain without any manual code.

```python
topic = TitleIndexedTopic()

# Publish multiple messages in a single call
# constitution-state is auto-injected as a MessageAttribute on each message
await topic.publish([
    {'content': {'id': 'id1', 'title': 'Title 1'}, 'attributes': {'type': 'created'}},
    {'content': {'id': 'id2', 'title': 'Title 2'}, 'attributes': {'type': 'updated'}},
    {'content': {'id': 'id3', 'title': 'Title 3'}},  # attributes are optional
])
```

### SNS - Message Attributes for Filtering

Use `attributes` to filter which SQS subscriptions receive each message:

```python
class EventTopic(SNSPublisher):
    def __init__(self):
        super().__init__(topic_arn=os.getenv('EVENTS_SNS_TOPIC_ARN'))

    def build_message(self, payload, event_type, priority='normal'):
        return {
            'content': payload,
            'attributes': {
                'event_type': event_type,   # SQS subscriptions can filter on this
                'priority': priority
            }
        }

# Usage
topic = EventTopic()
await topic.publish(topic.build_message(
    payload={'order_id': '123', 'amount': 99.99},
    event_type='order_created',
    priority='high'
))
```

### Fargate - Run multiple tasks

```python
executor = FargateExecutor()
task_arns = executor.run_task_batch(
    'search-tax-by-town',
    [
        {'TOWN': 'Norwalk'},
        {'TOWN': 'Stamford'},
        {'TOWN': 'Bridgeport'}
    ]
)
```

### Fargate - Check task status

```python
executor = FargateExecutor()
task_arn = executor.run_task('my-task', {'PARAM': 'value'})

# Check task status
status = executor.get_task_status(task_arn)
print(f"Status: {status['status']}")
print(f"Started at: {status['started_at']}")
```

### JSON Utilities for MongoDB Types

When returning MongoDB documents in API responses or exporting data, use the built-in serializers to handle `ObjectId`, `datetime`, `Decimal128`, and other BSON types:

```python
import json
from aws_python_helper.utils.json_encoder import MongoJSONEncoder, mongo_json_dumps
from aws_python_helper.utils.serializer import serialize_mongo_types

# Use as json.dumps cls parameter
json_str = json.dumps(my_mongo_doc, cls=MongoJSONEncoder)

# Helper function
json_str = mongo_json_dumps(my_mongo_doc)

# Convert a document in-place (dict → JSON-serializable dict)
clean_doc = serialize_mongo_types(my_mongo_doc)
```

Types automatically converted:

| MongoDB Type | Converts to |
|-------------|-------------|
| `ObjectId` | `str` |
| `datetime` | ISO 8601 string |
| `date` | ISO 8601 string |
| `Decimal128` | `float` |
| `Decimal` | `float` |
| `Binary` | base64 `str` |
| `UUID` | `str` |
| `bytes` | base64 `str` |
| `set` | `list` |

**Common use case** — exporting query results to JSON files:

```python
from aws_python_helper.utils.json_encoder import MongoJSONEncoder

class ExportResultsAPI(API):
    async def process(self):
        records = await self.db.orders_db.orders.find({}).to_list(1000)

        # Write to file with MongoJSONEncoder
        with open('/tmp/export.json', 'w') as f:
            json.dump(records, f, cls=MongoJSONEncoder, ensure_ascii=False, indent=2)
```

## 🤝 Contributing

If you find bugs or want to add features, please create a PR!

## 📄 License

MIT
