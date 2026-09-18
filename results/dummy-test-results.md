| Classification | Confidence | Duplicate | Overlap | Left model | Right model | Shared tables | Shared columns | Shared measures |
|---|---|---:|---:|---|---|---:|---:|---:|
| likely_duplicate | high | 1.0000 | 1.0000 | Dummy Enterprise BI / Contoso Sales Certified | Dummy Executive Reporting / Contoso Sales Executive Copy | 5 | 16 | 5 |
| high_overlap | high | 0.7722 | 0.8550 | Dummy Enterprise BI / Contoso Sales Certified | Dummy Regional Sales / Contoso Sales Regional Extended | 5 | 16 | 3 |
| high_overlap | high | 0.7722 | 0.8550 | Dummy Executive Reporting / Contoso Sales Executive Copy | Dummy Regional Sales / Contoso Sales Regional Extended | 5 | 16 | 3 |

## Common objects

### 1. Dummy Enterprise BI / Contoso Sales Certified <-> Dummy Executive Reporting / Contoso Sales Executive Copy

- **Tables:** `customer`, `date`, `geography`, `product`, `sales`
- **Columns:** `customer[customerkey] (int64)`, `customer[customername] (string)`, `customer[segment] (string)`, `date[datekey] (int64)`, `date[fiscalmonth] (string)`, `date[fiscalyear] (int64)`, `geography[country] (string)`, `geography[geographykey] (int64)`, `product[category] (string)`, `product[productkey] (int64)`, `sales[customerkey] (int64)`, `sales[discountamount] (decimal)`, `sales[orderdatekey] (int64)`, `sales[productkey] (int64)`, `sales[revenueamount] (decimal)`, `sales[saleskey] (int64)`
- **Measures:** `sales[average revenue per customer]`, `sales[discount rate]`, `sales[net revenue]`, `sales[revenue ytd]`, `sales[total revenue]`

### 2. Dummy Enterprise BI / Contoso Sales Certified <-> Dummy Regional Sales / Contoso Sales Regional Extended

- **Tables:** `customer`, `date`, `geography`, `product`, `sales`
- **Columns:** `customer[customerkey] (int64)`, `customer[customername] (string)`, `customer[segment] (string)`, `date[datekey] (int64)`, `date[fiscalmonth] (string)`, `date[fiscalyear] (int64)`, `geography[country] (string)`, `geography[geographykey] (int64)`, `product[category] (string)`, `product[productkey] (int64)`, `sales[customerkey] (int64)`, `sales[discountamount] (decimal)`, `sales[orderdatekey] (int64)`, `sales[productkey] (int64)`, `sales[revenueamount] (decimal)`, `sales[saleskey] (int64)`
- **Measures:** `sales[net revenue]`, `sales[revenue ytd]`, `sales[total revenue]`

### 3. Dummy Executive Reporting / Contoso Sales Executive Copy <-> Dummy Regional Sales / Contoso Sales Regional Extended

- **Tables:** `customer`, `date`, `geography`, `product`, `sales`
- **Columns:** `customer[customerkey] (int64)`, `customer[customername] (string)`, `customer[segment] (string)`, `date[datekey] (int64)`, `date[fiscalmonth] (string)`, `date[fiscalyear] (int64)`, `geography[country] (string)`, `geography[geographykey] (int64)`, `product[category] (string)`, `product[productkey] (int64)`, `sales[customerkey] (int64)`, `sales[discountamount] (decimal)`, `sales[orderdatekey] (int64)`, `sales[productkey] (int64)`, `sales[revenueamount] (decimal)`, `sales[saleskey] (int64)`
- **Measures:** `sales[net revenue]`, `sales[revenue ytd]`, `sales[total revenue]`
