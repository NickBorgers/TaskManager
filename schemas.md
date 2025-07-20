# Notion Task DB

```mermaid
---
title: Template Tasks and Active Tasks
---
classDiagram
    class TemplateTask {
        +Text id
        +Text Task 
        +Select Priority
        +Select Frequency
        +Select Category
        +Url Documentation*
        +Date LastCompleted*
    }

    class ActiveTask {
        +Text id
        +Text Task 
        +Select Priority
        +Select Category
        +Url Documentation*
        +Status Status
        +Date CreationDate
        +Date PlannedDate
        +Date CompletedDate
    }

    TemplateTask "1" --> "many" ActiveTask : creates

```