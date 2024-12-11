install.packages("readxl")
install.packages("ggplot2")

library(readxl)
library(ggplot2)

file_path <- "stats.xlsx"
data <- read_excel(file_path)

# 막대그래프 그리기
ggplot(data, aes(x = Region)) +
  geom_bar(aes(y = Hotel), stat = "identity", fill = "blue", position = "dodge") +
  geom_bar(aes(y = Residence), stat = "identity", fill = "green", position = "dodge") +
  geom_bar(aes(y = Motel), stat = "identity", fill = "red", position = "dodge") +
  geom_bar(aes(y = Hostel), stat = "identity", fill = "purple", position = "dodge") +
  geom_bar(aes(y = GuestHouse), stat = "identity", fill = "orange", position = "dodge") +
  geom_bar(aes(y = Apartment), stat = "identity", fill = "yellow", position = "dodge") +
  geom_bar(aes(y = Pension), stat = "identity", fill = "brown", position = "dodge") +
  geom_bar(aes(y = Homestay), stat = "identity", fill = "pink", position = "dodge") +
  geom_bar(aes(y = BedAndBreakfast), stat = "identity", fill = "cyan", position = "dodge") +
  geom_bar(aes(y = Villa), stat = "identity", fill = "gray", position = "dodge") +
  labs(title = "숙박시설 현황",
       x = "지역",
       y = "숙박시설 수") +
  theme_minimal()
