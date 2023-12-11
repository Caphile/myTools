library(readxl)
library(ggplot2)

data <- read_excel("combined_data.xlsx")



groupby_relation_results <- aggregate(cbind(correctness, response_time) ~ relation, data, mean)
print(groupby_relation_results)



groupby_conditions_results <- aggregate(cbind(correctness, response_time) ~ relation + prime_condition + target_condition, data, mean)
print(groupby_conditions_results)



orderby_conditions_results <- groupby_conditions_results[order(-groupby_conditions_results$response_time), ]

ggplot(orderby_conditions_results, aes(x = reorder(interaction(relation, prime_condition, target_condition), -response_time), y = response_time)) +
  geom_bar(stat = "identity") +
  theme(axis.text.x = element_text(angle = 90, hjust = 1)) +
  labs(x = "Relation and Conditions", y = "Response Time", title = "Response Time by Relation and Conditions")



artifactual_data <- subset(data, prime_condition == "artifactual" | target_condition == "artifactual")
artifactual_summary <- aggregate(cbind(correctness, response_time) ~ relation + prime_condition + target_condition, artifactual_data, mean)
print(artifactual_summary)

artifactual_summary_means <- colMeans(artifactual_summary[, c("correctness", "response_time")])
print(artifactual_summary_means)



natural_data <- subset(data, prime_condition == "natural" | target_condition == "natural")
natural_summary <- aggregate(cbind(correctness, response_time) ~ relation + prime_condition + target_condition, natural_data, mean)
print(natural_summary)

natural_summary_means <- colMeans(natural_summary[, c("correctness", "response_time")])
print(natural_summary_means)