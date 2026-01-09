# AWS Python Framework

Mini-framework to create REST APIs, SQS Consumers, SNS Publishers, and Fargate Tasks with Python in AWS Lambda.

## 🚀 Features

- **Reusable single handler**: A single handler for all your API routes
- **Dynamic controller loading**: Routing based on convention
- **OOP structure**: Object-oriented programming for your code
- **Flexible MongoDB**: Direct access to multiple databases without models
- **SQS Consumers**: Same pattern to process SQS messages
- **SNS Publishers**: Same pattern to publish messages to SNS topics
- **Fargate Tasks**: Same pattern to run tasks in Fargate containers
- **Type hints**: Modern Python with type annotations
- **Async/await**: Full support for asynchronous operations

## 🔧 Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure MongoDB URI
export MONGODB_URI="mongodb://localhost:27017"
```

## 📝 Basic Usage

### Create an Endpoint

**1. Create your API class** in `src/api/constitutions/list.py`:

```python
from aws_python_framework.api.base import API

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
from aws_python_framework.api.handler import lambda_handler
handler = lambda_handler
```

### Create an SQS Consumer

**1. Create your consumer** in `src/consumers/title_indexed.py`:

```python
from aws_python_framework.sqs.consumer_base import SQSConsumer

class TitleIndexedConsumer(SQSConsumer):
    async def process_record(self, record):
        body = self.parse_body(record)
        # Your logic here
        await self.db.constitution_db.titles.insert_one(body)
```

**2. Configure the handler** in `src/handlers/sqs_handler.py`:

```python
from aws_python_framework.sqs.handler import sqs_handler

# Create a handler for each consumer and export it
title_indexed_handler = sqs_handler('title-indexed')

__all__ = ['title_indexed_handler']
```

### Publish to SNS

**1. Create your topic** in `src/topics/title_indexed.py`:

```python
from lambda_framework.sns.publisher import SNSPublisher
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
from aws_python_framework.fargate.task_base import FargateTask

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
from aws_python_framework.fargate.handler import fargate_handler
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
COPY aws_python_framework /app/aws_python_framework
COPY config.py /app/config.py
COPY tasks /app/tasks
COPY tasks/search_tax_by_town/main.py /app/main.py

ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
```

**4. Invoke from Lambda**:

```python
from aws_python_framework.fargate.executor import FargateExecutor

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
from aws_python_framework.api.base import API

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
