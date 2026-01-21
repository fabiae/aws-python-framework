# 📁 Framework Structure Guide

Complete guide for the folder structure and naming conventions of the AWS Python Helper framework.

## 🗂️ Complete Project Structure

```
your-project/
├── src/
│   ├── api/                                # REST APIs
│   │   ├── users/
│   │   │   ├── get.py                     # GET /users/123
│   │   │   ├── list.py                    # GET /users
│   │   │   ├── post.py                    # POST /users
│   │   │   ├── put.py                     # PUT /users/123
│   │   │   └── delete.py                  # DELETE /users/123
│   │   └── orders/
│   │       ├── get.py
│   │       └── list.py
│   │
│   ├── consumer/                          # SQS Consumers (direct files)
│   │   ├── user_created.py                # UserCreatedConsumer
│   │   ├── order_processed.py             # OrderProcessedConsumer
│   │   └── payment_completed.py           # PaymentCompletedConsumer
│   │
│   ├── lambda/                             # Standalone Lambdas (folders)
│   │   ├── GenerateRoute/
│   │   │   └── main.py                    # GenerateRouteLambda
│   │   ├── SyncCarrier/
│   │   │   └── main.py                    # SyncCarrierLambda
│   │   └── ProcessPayment/
│   │       └── main.py                    # ProcessPaymentLambda
│   │
│   ├── task/                              # Fargate Tasks (folders)
│   │   ├── search-tax-by-town/
│   │   │   ├── main.py                    # Entry point
│   │   │   └── task.py                    # SearchTaxByTownTask
│   │   └── process-data/
│   │       ├── main.py
│   │       └── task.py                    # ProcessDataTask
│   │
│   ├── topics/                             # SNS Publishers
│   │   ├── user_created.py
│   │   └── order_completed.py
│   │
│   └── handlers/                           # Lambda Handlers
│       ├── api_handler.py                 # For APIs
│       ├── sqs_handler.py                 # For SQS Consumers
│       └── lambda_handler.py              # For Standalone Lambdas
│
└── requirements.txt
```

## 📋 Naming Convention Table

### APIs

| HTTP Method | URL | File Path | Class Name |
|-------------|-----|-----------|------------|
| GET | `/users` | `src/api/users/list.py` | `UsersListAPI` |
| GET | `/users/123` | `src/api/users/get.py` | `UsersGetAPI` |
| POST | `/users` | `src/api/users/post.py` | `UsersPostAPI` |
| PUT | `/users/123` | `src/api/users/put.py` | `UsersPutAPI` |
| DELETE | `/users/123` | `src/api/users/delete.py` | `UsersDeleteAPI` |

**Conventions:**
- Folders use **kebab-case** (e.g., `users/`, `user-profiles/`)
- Files use **method names** (`get.py`, `list.py`, `post.py`, etc.)
- Classes use **PascalCase + API** suffix

### SQS Consumers

| Handler Name (kebab-case) | File Path | Class Name |
|---------------------------|-----------|------------|
| `user-created` | `src/consumer/user_created.py` | `UserCreatedConsumer` |
| `order-processed` | `src/consumer/order_processed.py` | `OrderProcessedConsumer` |
| `payment-completed` | `src/consumer/payment_completed.py` | `PaymentCompletedConsumer` |

**Conventions:**
- Handler names use **kebab-case**
- Files use **snake_case**
- Classes use **PascalCase + Consumer** suffix
- Files are **direct** (not in folders) for simplicity

### Standalone Lambdas

| Handler Name (kebab-case) | Folder Path | File | Class Name |
|---------------------------|-------------|------|------------|
| `generate-route` | `src/lambda/GenerateRoute/` | `main.py` | `GenerateRouteLambda` |
| `sync-carrier` | `src/lambda/SyncCarrier/` | `main.py` | `SyncCarrierLambda` |
| `process-payment` | `src/lambda/ProcessPayment/` | `main.py` | `ProcessPaymentLambda` |

**Conventions:**
- Handler names use **kebab-case**
- Folders use **PascalCase**
- File is always `main.py`
- Classes use **PascalCase + Lambda** suffix

### Fargate Tasks

| Handler Name (kebab-case) | Folder Path | Files | Class Name |
|---------------------------|-------------|-------|------------|
| `search-tax-by-town` | `src/task/search-tax-by-town/` | `main.py`, `task.py` | `SearchTaxByTownTask` |
| `process-data` | `src/task/process-data/` | `main.py`, `task.py` | `ProcessDataTask` |

**Conventions:**
- Handler names use **kebab-case**
- Folders use **kebab-case**
- Has two files: `main.py` (entry point) and `task.py` (class)
- Classes use **PascalCase + Task** suffix

## 🎯 Complete Examples

### API Example
```python
# src/api/users/list.py
from aws_python_helper.api.base import API

class UsersListAPI(API):
    async def process(self):
        users = await self.db.users_db.users.find().to_list(100)
        self.set_body(users)
```

**Handler:**
```python
# src/handlers/api_handler.py
from aws_python_helper.api.handler import api_handler
handler = api_handler
```

### SQS Consumer Example
```python
# src/consumer/user_created.py
from aws_python_helper.sqs.consumer_base import SQSConsumer

class UserCreatedConsumer(SQSConsumer):
    async def process_record(self, record):
        body = self.parse_body(record)
        await self.db.users_db.users.insert_one(body)
```

**Handler:**
```python
# src/handlers/sqs_handler.py
from aws_python_helper.sqs.handler import sqs_handler

user_created_handler = sqs_handler('user-created')

__all__ = ['user_created_handler']
```

### Standalone Lambda Example
```python
# src/lambda/GenerateRoute/main.py
from aws_python_helper.lambda_standalone.base import Lambda

class GenerateRouteLambda(Lambda):
    async def validate(self):
        if 'shipping_id' not in self.data:
            raise ValueError("shipping_id is required")
    
    async def process(self):
        shipping_id = self.data['shipping_id']
        # Your logic here
        return {'route_id': 'route123'}
```

**Handler:**
```python
# src/handlers/lambda_handler.py
from aws_python_helper.lambda_standalone.handler import lambda_handler

generate_route_handler = lambda_handler('generate-route')

__all__ = ['generate_route_handler']
```

### Fargate Task Example
```python
# src/task/search-tax-by-town/task.py
from aws_python_helper.fargate.task_base import FargateTask

class SearchTaxByTownTask(FargateTask):
    async def execute(self):
        town = self.require_env('TOWN')
        # Your logic here
        pass
```

**Entry Point:**
```python
# src/task/search-tax-by-town/main.py
from aws_python_helper.fargate.handler import fargate_handler
import sys

if __name__ == '__main__':
    exit_code = fargate_handler('search-tax-by-town')
    sys.exit(exit_code)
```

## ⚡ Quick Reference

| Component | Naming | Structure | Class Suffix |
|-----------|--------|-----------|--------------|
| **API** | kebab-case folder | `src/api/{resource}/{method}.py` | `API` |
| **Consumer** | kebab-case handler | `src/consumer/{name}.py` | `Consumer` |
| **Lambda** | kebab-case handler | `src/lambda/{PascalCase}/main.py` | `Lambda` |
| **Task** | kebab-case handler | `src/task/{kebab-case}/task.py` | `Task` |

## 🔄 Conversion Examples

**From handler name to file/folder:**

```
Handler: 'user-created'
→ Consumer: src/consumers/user_created.py (snake_case file)
→ Class: UserCreatedConsumer

Handler: 'generate-route'
→ Lambda: src/lambda/GenerateRoute/main.py (PascalCase folder)
→ Class: GenerateRouteLambda

Handler: 'search-tax-by-town'
→ Task: src/tasks/search-tax-by-town/task.py (kebab-case folder)
→ Class: SearchTaxByTownTask
```

## 📝 Notes

- **Why different conventions?**
  - Consumers as files: Simple, most don't need multiple files
  - Lambdas in PascalCase folders: Easy to identify in deployment
  - Tasks in kebab-case folders: Consistent with URL patterns
  
- **Scalability**: If a consumer grows complex, you can convert it to a folder structure later without breaking the framework

- **Class detection**: The framework automatically finds your class by checking for methods like `process()`, `process_record()`, or `execute()`
