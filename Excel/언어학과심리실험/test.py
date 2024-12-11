def list_flatten(origin) :
  flat_list = []
  for i in origin :
    if type(i) == list:
        for j in i:
            flat_list.append(j)
    else :
        flat_list.append(i)

  print('{}를 평탄화하면\n{}입니다.'.format(list, flat_list))

list_b = [1, 2, [3, 4], 5, [6, 7], [8, 9]]
list_flatten(list_b)