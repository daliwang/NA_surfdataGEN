with open('output.log111123', 'r') as file:
    lines = file.readlines()

Var_name = ""
for i in range(len(lines)):
    if lines[i].startswith("Working on varibale: "):
        Var_name = lines[i].split(" ")[3]
        #print("scanning ",Var_name, "at line: ", str(i))
        
    elif lines[i].startswith("o_data, f_data1, f_data, dst: max/min/sum"):
        for j in range(i+1, i+4):
            val1, val2, val3, val4 = map(float, lines[j].split())
            if val2 != val3 or val3 != val4:
                print(val2, val3, val4) 
                print("Differences found with variable " + Var_name + "(at line) "+ str(j))
