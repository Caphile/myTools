library(readxl)

data <- read_excel("combined_data.xlsx")

orderby_relation_results <- aggregate(cbind(correctness, response_time) ~ relation, data, mean)

print(orderby_relation_results)

orderby_conditions_results <- aggregate(cbind(correctness, response_time) ~ relation + prime_condition + target_condition, data, mean)

print(orderby_conditions_results)
