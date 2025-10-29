# School Library Management Data Dictionary (MySQL)

This document describes the MySQL schema for the School Library Management system. It is derived from the original SQL Server DDL and adapts data types and default behaviors for MySQL 8.0.

## Table: `T_Book`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for each book record. |
| `BookName` | VARCHAR(255) | YES | NULL | Title of the book. |
| `ISBN` | VARCHAR(255) | YES | NULL | International Standard Book Number associated with the book. |
| `Position` | VARCHAR(255) | YES | NULL | Physical shelf location or position for the book. |
| `Category1` | INT UNSIGNED | YES | NULL | Primary category ID referencing `T_Category.Id`. |
| `Category2` | INT UNSIGNED | YES | NULL | Secondary category ID for hierarchical classification. |
| `Category3` | INT UNSIGNED | YES | NULL | Tertiary category ID for detailed classification. |
| `Amount` | INT | YES | NULL | Total quantity of this book owned by the library. |
| `LendAmount` | INT | YES | NULL | Number of copies currently lent out. |
| `Price` | DECIMAL(10,2) | YES | 0.00 | Purchase price of a single copy. |
| `Public` | VARCHAR(255) | YES | NULL | Publisher name. |
| `Writer` | VARCHAR(255) | YES | NULL | Author of the book. |
| `Version` | VARCHAR(255) | YES | NULL | Edition or version information. |
| `Source` | VARCHAR(255) | YES | NULL | Source of acquisition (donation, purchase, etc.). |
| `IsDelete` | TINYINT(1) | YES | 0 | Logical deletion flag (1 indicates deleted). |
| `CreateTime` | DATETIME | YES | CURRENT_TIMESTAMP | Record creation time. |
| `AddPerson` | VARCHAR(255) | YES | NULL | Operator who created the record. |
| `UpdateTime` | DATETIME | YES | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | Timestamp of the most recent update. |
| `UpdatePerson` | VARCHAR(255) | YES | NULL | Operator who last updated the record. |
| `Comp` | INT | YES | NULL | Company or campus identifier for multi-tenant scenarios. |
| `IndexId` | VARCHAR(255) | YES | NULL | Library indexing identifier (e.g., classification code). |
| `pages` | INT | YES | NULL | Total number of pages in the book. |
| `images` | VARCHAR(500) | YES | NULL | Relative or absolute path to book cover images. |
| `summary` | VARCHAR(500) | YES | NULL | Short description or summary of the book. |
| `inputNum` | INT | YES | NULL | Accession number or internal input order. |
| `remark` | VARCHAR(2000) | YES | NULL | Additional notes about the book. |
| `isBulk` | TINYINT(1) | YES | NULL | Indicates whether the book was part of a bulk acquisition. |

**Primary Key:** `PK_T_Book` on (`id`)

## Table: `T_Category`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `Id` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for the category. |
| `CategoryName` | VARCHAR(255) | YES | NULL | Name of the category. |
| `ParentId` | INT UNSIGNED | YES | NULL | ID of the parent category for hierarchical grouping. |
| `isDelete` | TINYINT(1) | YES | 0 | Logical deletion flag (1 indicates deleted). |
| `Comp` | INT | YES | NULL | Company or campus identifier. |
| `Sort` | INT | YES | 0 | Ordering value when displaying categories. |

**Primary Key:** `PK_T_Category` on (`Id`)

## View: `V_CategoryBook`

Aggregates book quantities and inventory value by primary category. Only records where `T_Book.IsDelete <> 1` are included.

| Column | Type | Description |
| --- | --- | --- |
| `CategoryId` | INT UNSIGNED | Category ID grouping the aggregation. |
| `sumnum` | INT | Total count of books within the category. |
| `sumprice` | DECIMAL(18,2) | Sum of (`Amount` × `Price`) for books in the category. |
| `CategoryName` | VARCHAR(255) | Name of the category. |

## Table: `T_back`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for a return transaction. |
| `LendId` | INT UNSIGNED | YES | NULL | ID of the lending record associated with the return (`T_lend.id`). |
| `Amount` | INT | YES | 0 | Number of copies returned in this transaction. |
| `createTime` | DATETIME | YES | CURRENT_TIMESTAMP | Timestamp when the return was recorded. |
| `operAdmin` | VARCHAR(255) | YES | NULL | Administrator who processed the return. |
| `status` | TINYINT(1) | YES | 0 | Processing status of the return (0 pending, 1 completed, etc.). |
| `comment` | TEXT | YES | NULL | Additional notes about the return. |
| `isDelete` | TINYINT(1) | YES | 0 | Logical deletion flag. |
| `Comp` | INT | YES | NULL | Company or campus identifier. |

**Primary Key:** `PK_T_back` on (`id`)

## Table: `T_lend`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for a lending transaction. |
| `BookId` | INT UNSIGNED | YES | NULL | ID of the borrowed book (`T_Book.id`). |
| `ReaderId` | INT UNSIGNED | YES | NULL | ID of the reader borrowing the book (`T_reader.id`). |
| `Amount` | INT | YES | 0 | Number of copies lent in the transaction. |
| `CreateTime` | DATETIME | YES | CURRENT_TIMESTAMP | Date and time when the book was lent out. |
| `DueDate` | DATETIME | YES | CURRENT_TIMESTAMP | Expected return date. |
| `OperAdmin` | VARCHAR(255) | YES | NULL | Administrator who processed the lending. |
| `Status` | TINYINT(1) | YES | 0 | Current status of the lending (0 active, 1 returned, etc.). |
| `Comment` | TEXT | YES | NULL | Additional remarks for the lending transaction. |
| `Comp` | INT | YES | NULL | Company or campus identifier. |
| `isDelete` | TINYINT(1) | YES | 0 | Logical deletion flag. |

**Primary Key:** `PK_T_lend` on (`id`)

## View: `V_lend`

Provides enriched lending information by joining lending, reader, return, book, and category data.

| Column | Type | Description |
| --- | --- | --- |
| `id` | INT UNSIGNED | Lending transaction ID. |
| `BookName` | VARCHAR(255) | Title of the lent book. |
| `BookId` | INT UNSIGNED | Reference to the book ID. |
| `ISBN` | VARCHAR(255) | ISBN of the lent book. |
| `Amount` | INT | Number of copies lent. |
| `lbTime` | VARCHAR(33) | Concatenated string of lending and return timestamps (`CreateTime` + `createTime`). |
| `DueDate` | DATETIME | Expected return date. |
| `uid` | INT UNSIGNED | Reader ID. |
| `CardNo` | VARCHAR(255) | Library card number of the reader. |
| `ReaderName` | VARCHAR(255) | Name of the reader. |
| `Status` | TINYINT(1) | Lending status indicator. |
| `isDelete` | TINYINT(1) | Logical deletion flag for the lending record. |
| `Comp` | INT | Company or campus identifier. |
| `Position` | VARCHAR(255) | Physical location of the book. |
| `CreateTime` | DATETIME | Time when the lending record was created. |
| `CategoryName` | VARCHAR(255) | Primary category of the book. |

## Table: `T_reader`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for a reader. |
| `CardNo` | VARCHAR(255) | YES | NULL | Library card number. |
| `ReaderName` | VARCHAR(255) | YES | NULL | Full name of the reader. |
| `ReaderSex` | VARCHAR(255) | YES | NULL | Gender of the reader. |
| `ReaderPhone` | VARCHAR(255) | YES | NULL | Contact phone number. |
| `ReaderCerti` | VARCHAR(255) | YES | NULL | Type of identification certificate. |
| `ReaderCertiNum` | VARCHAR(255) | YES | NULL | Identification certificate number. |
| `ReaderExpire` | DATETIME | YES | CURRENT_TIMESTAMP | Expiration date of the reader's membership. |
| `ReaderGroup` | VARCHAR(255) | YES | NULL | Reader grouping (e.g., student, teacher). |
| `isDelete` | TINYINT(1) | YES | 0 | Logical deletion flag. |
| `Status` | TINYINT(1) | YES | 0 | Status of the reader account (0 active, 1 suspended). |
| `Comp` | INT | YES | NULL | Company or campus identifier. |
| `UpdateUser` | VARCHAR(255) | YES | NULL | Administrator who last updated the record. |
| `UpdateTime` | DATETIME | YES | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | Timestamp of the last update. |
| `ClassName` | VARCHAR(255) | YES | NULL | Legacy class name stored directly in the reader record. |
| `classid` | INT UNSIGNED | YES | NULL | Foreign key to `T_Class.ClassId`. |

**Primary Key:** `PK_T_reader` on (`id`)

## View: `v_reader`

Combines reader information with class and grade metadata.

| Column | Type | Description |
| --- | --- | --- |
| `id` | INT UNSIGNED | Reader ID. |
| `CardNo` | VARCHAR(255) | Library card number. |
| `ReaderName` | VARCHAR(255) | Reader name. |
| `ReaderSex` | VARCHAR(255) | Reader gender. |
| `ReaderPhone` | VARCHAR(255) | Reader contact phone. |
| `ReaderCerti` | VARCHAR(255) | Type of identification certificate. |
| `ReaderCertiNum` | VARCHAR(255) | Identification certificate number. |
| `ReaderExpire` | DATETIME | Membership expiration time. |
| `ReaderGroup` | VARCHAR(255) | Reader grouping. |
| `isDelete` | TINYINT(1) | Logical deletion flag. |
| `Status` | TINYINT(1) | Reader status. |
| `Comp` | INT | Company or campus identifier. |
| `UpdateUser` | VARCHAR(255) | Last operator who updated the reader. |
| `UpdateTime` | DATETIME | Timestamp of the last reader update. |
| `OldClassName` | VARCHAR(255) | Original class name stored in `T_reader.ClassName`. |
| `classid` | INT UNSIGNED | Class identifier. |
| `ClassName` | VARCHAR(50) | Current class name from `T_Class`. |
| `GradeName` | VARCHAR(50) | Grade name from `T_Grade`. |
| `GradeId` | INT UNSIGNED | Grade identifier. |

## Table: `T_Class`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `ClassId` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for a class. |
| `ClassName` | VARCHAR(50) | YES | NULL | Name of the class. |
| `GradeId` | INT UNSIGNED | YES | NULL | Foreign key referencing `T_Grade.GradeId`. |
| `isdelete` | TINYINT(1) | YES | 0 | Logical deletion flag. |

**Primary Key:** `PK_T_Class` on (`ClassId`)

## View: `V_Class`

Provides a class listing with associated grade information.

| Column | Type | Description |
| --- | --- | --- |
| `ClassId` | INT UNSIGNED | Class identifier. |
| `ClassName` | VARCHAR(50) | Class name. |
| `GradeId` | INT UNSIGNED | Grade identifier. |
| `isdelete` | TINYINT(1) | Logical deletion flag. |
| `GradeName` | VARCHAR(50) | Grade name. |

## Table: `T_Grade`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `GradeId` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for a grade level. |
| `GradeName` | VARCHAR(50) | YES | NULL | Name of the grade (e.g., Grade 1). |
| `isdelete` | TINYINT(1) | YES | 0 | Logical deletion flag. |

**Primary Key:** `PK_T_Grade` on (`GradeId`)

## Table: `Log`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for the log entry. |
| `funcName` | VARCHAR(2000) | YES | NULL | Name of the function or module that generated the log. |
| `msg` | VARCHAR(4000) | YES | NULL | Log message content. |
| `createtime` | DATETIME | YES | CURRENT_TIMESTAMP | Time when the log entry was created. |

**Primary Key:** `PK_Log` on (`id`)

## Table: `T_Admin`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `Id` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for an administrator. |
| `UserId` | VARCHAR(255) | YES | NULL | Administrator login identifier. |
| `Name` | VARCHAR(255) | YES | NULL | Administrator display name. |
| `pwd` | VARCHAR(255) | YES | NULL | Password hash for the administrator account. |
| `lvl` | VARCHAR(255) | YES | NULL | Role level or permission tier. |
| `isdelete` | TINYINT(1) | YES | 0 | Logical deletion flag. |
| `LastLogin` | DATETIME | YES | CURRENT_TIMESTAMP | Timestamp of the last successful login. |
| `Comp` | INT | YES | NULL | Company or campus identifier. |

**Primary Key:** `PK_T_Admin` on (`Id`)

## Table: `T_position`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `Id` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for a storage position record. |
| `PositionName` | VARCHAR(255) | YES | NULL | Name or code of the storage position. |
| `isDelete` | TINYINT(1) | YES | 0 | Logical deletion flag. |
| `Sort` | INT | YES | 0 | Display order of the position. |
| `Comp` | INT | YES | NULL | Company or campus identifier. |

**Primary Key:** `PK_T_position` on (`Id`)

## Table: `T_trans`

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | INT UNSIGNED AUTO_INCREMENT | NO | — | Unique identifier for an inventory transaction. |
| `Bookid` | INT UNSIGNED | YES | NULL | ID of the book affected by the transaction (`T_Book.id`). |
| `amount` | INT | YES | 0 | Quantity adjustment (positive or negative). |
| `Source` | VARCHAR(255) | YES | NULL | Source or type of transaction (e.g., purchase, donation). |
| `createTime` | DATETIME | YES | CURRENT_TIMESTAMP | Timestamp when the transaction was recorded. |
| `operAdmin` | VARCHAR(255) | YES | NULL | Administrator who recorded the transaction. |
| `comment` | TEXT | YES | NULL | Additional notes regarding the transaction. |
| `isdelete` | TINYINT(1) | YES | 0 | Logical deletion flag. |
| `Comp` | INT | YES | NULL | Company or campus identifier. |

**Primary Key:** `PK_T_trans` on (`id`)

