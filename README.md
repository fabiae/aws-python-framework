# AWS Python Framework

Mini-framework to create REST APIs, SQS Consumers, SNS Publishers, Fargate Tasks, and Standalone Lambdas with Python in AWS Lambda.

## 🚀 Features

- **Reusable single handler**: A single handler for all your API routes
- **Dynamic controller loading**: Routing based on convention
- **OOP structure**: Object-oriented programming for your code
- **Flexible MongoDB**: Direct access to multiple databases without models
- **SQS Consumers**: Same pattern to process SQS messages
- **SNS Publishers**: Same pattern to publish messages to SNS topics
- **Fargate Tasks**: Same pattern to run tasks in Fargate containers
- **Standalone Lambdas**: Create lambdas invocable directly with AWS SDK
- **Type hints**: Modern Python with type annotations
- **Async/await**: Full support for asynchronous operations

## 🔧 Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure MongoDB URI
export MONGODB_URI="mongodb://localhost:27017"
```

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
    │   ├── GenerateRoute/             # generate-route -> GenerateRouteLambda
    │   │   └── main.py
    │   ├── SyncCarrier/               # sync-carrier -> SyncCarrierLambda
    │   │   └── main.py
    │   └── ProcessPayment/            # process-payment -> ProcessPaymentLambda
    │       └── main.py
    │
    └── task/                         # Fargate Tasks (folders)
        ├── search-tax-by-town/        # search-tax-by-town -> SearchTaxByTownTask
        │   ├── main.py                # Entry point
        │   └── task.py                # Task class
        └── process-data/              # process-data -> ProcessDataTask
            ├── main.py
            └── task.py
```

### Naming Conventions

The framework uses automatic class name detection based on your folder/file structure:

| Type | Handler Name | File Path | Class Name |
|------|--------------|-----------|------------|
| **API** | N/A | `src/api/users/list.py` | `UsersListAPI` |
| **Consumer** | `user-created` | `src/consumer/user_created.py` | `UserCreatedConsumer` |
| **Lambda** | `generate-route` | `src/lambda/GenerateRoute/main.py` | `GenerateRouteLambda` |
| **Task** | `search-tax-by-town` | `src/task/search-tax-by-town/task.py` | `SearchTaxByTownTask` |

**Rules:**
- Handler names use **kebab-case** (e.g., `user-created`, `generate-route`)
- Consumer files use **snake_case** (e.g., `user_created.py`)
- Lambda folders use **PascalCase** (e.g., `GenerateRoute/`)
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

**1. Create your consumer** in `src/consumers/title_indexed.py`:

```python
from aws_python_helper.sqs.consumer_base import SQSConsumer

class TitleIndexedConsumer(SQSConsumer):
    async def process_record(self, record):
        body = self.parse_body(record)
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

**1. Create your lambda class** in `src/lambda/GenerateRoute/main.py`:

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
- Folder: `src/lambda/GenerateRoute/` (PascalCase)
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
| `generate-route` | `src/lambda/GenerateRoute/` | `main.py` | `GenerateRouteLambda` |
| `sync-carrier` | `src/lambda/SyncCarrier/` | `main.py` | `SyncCarrierLambda` |
| `process-payment` | `src/lambda/ProcessPayment/` | `main.py` | `ProcessPaymentLambda` |
| `send-notification` | `src/lambda/SendNotification/` | `main.py` | `SendNotificationLambda` |

**Common Use Cases:**
- Internal microservices communication
- Background data processing
- Integration with external services
- Scheduled tasks (with EventBridge)
- Step Functions workflows
- Cross-service operations

### Publish to SNS

**1. Create your topic** in `src/topics/title_indexed.py`:

```python
from aws_python_helper.sns.publisher import SNSPublisher
import os

class TitleIndexedTopic(SNSPublisher):
    def __init__(self):
        super().__init__(
            topic_arn=os.getenv('TITLE_INDEXED_SNS_TOPIC_ARN')
        )
    
    async def publish_indexed(self, constitution_id, title):
        await self.publish({
            'constitution_id': constitution_id,
            'title': title,
            'event_type': 'title_indexed'
        })
```

**2. Use the topic** from anywhere:

```python
from src.topics.title_indexed import TitleIndexedTopic

# In a consumer, API or task
topic = TitleIndexedTopic()
await topic.publish_indexed('123', 'My Constitution')
```

### Run a Fargate Task

**1. Create your task** in `src/tasks/search_tax_by_town/task.py`:

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

**2. Create the entry point** in `src/tasks/search_tax_by_town/main.py`:

```python
from aws_python_helper.fargate.handler import fargate_handler
import sys

if __name__ == '__main__':
    exit_code = fargate_handler('search-tax-by-town')
    sys.exit(exit_code)
```

**3. Create the Dockerfile** in `src/tasks/search_tax_by_town/Dockerfile`:

```dockerfile
FROM python:3.10.12-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/framework_requirements.txt
COPY src/tasks/search_tax_by_town/requirements.txt /app/task_requirements.txt
RUN pip install -r /app/framework_requirements.txt && \
    pip install -r /app/task_requirements.txt

# Copy code
COPY aws_python_helper /app/aws_python_helper
COPY config.py /app/config.py
COPY tasks /app/tasks
COPY tasks/search_tax_by_town/main.py /app/main.py

ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
```

**4. Invoke from Lambda**:

```python
from aws_python_helper.fargate.executor import FargateExecutor

def handler(event, context):
    executor = FargateExecutor()
    task_arn = executor.run_task(
        'search-tax-by-town',
        envs={'town': 'Norwalk', 'only_tax': 'true'}
    )
    return {'taskArn': task_arn}
```

## 🗄️ Access to MongoDB

The framework provides flexible access to multiple databases:

```python
class MyAPI(API):
    async def process(self):
        # Access to different databases
        user = await self.db.users_db.users.find_one({'_id': user_id})
        
        # Another database
        await self.db.analytics_db.logs.insert_one({'action': 'view'})
        
        # Multiple collections
        titles = await self.db.constitution_db.titles.find().to_list(100)
        articles = await self.db.constitution_db.articles.find().to_list(100)
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

**2. The standalone lambda** (`src/lambda/GenerateRoute/main.py`):

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

## 🔐 Environment Variables

```bash
# MongoDB Required Environment Variable
MONGODB_URI=mongodb://localhost:27017

## Rest Environment Variables
```

## 📊 Advanced Features

### SNS Publisher - Batch Publishing

```python
# Publish multiple messages
topic = TitleIndexedTopic()
await topic.publish_batch_indexed([
    {'constitution_id': 'id1', 'title': 'Title 1'},
    {'constitution_id': 'id2', 'title': 'Title 2'},
    {'constitution_id': 'id3', 'title': 'Title 3'}
])
```

### Fargate - Run multiple tasks

```python
executor = FargateExecutor()
task_arns = executor.run_task_batch(
    'search-tax-by-town',
    [
        {'town': 'Norwalk'},
        {'town': 'Stamford'},
        {'town': 'Bridgeport'}
    ]
)
```

### Fargate - Check task status

```python
executor = FargateExecutor()
task_arn = executor.run_task('my-task', {'param': 'value'})

# Check task status
status = executor.get_task_status(task_arn)
print(f"Status: {status['status']}")
print(f"Started at: {status['started_at']}")
```

### SNS - Message Attributes

```python
# Publish with attributes for SNS filtering
topic = ConstitutionCreatedTopic()
await topic.publish_created(
    constitution_id='123',
    title='New Constitution',
    country='Ecuador',
    year=2023,
    created_by='user_456',
    attributes={'priority': 'high', 'region': 'latam'}
)
```

## 🤝 Contributing

If you find bugs or want to add features, please create a PR!

## 📄 License

MIT
