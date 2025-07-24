# -*- coding: utf-8 -*-
"""
Natural Language Understanding
"""

# 对于模块和自己写的程序不在同一个目录下，可以把模块的路径通过 sys.path.append(路径) 添加到程序中
import sys
sys.path.append('/home/xieyang/anaconda3/lib/python3.10/site-packages')
#sys.path.append('/home/lmy/anaconda3/lib/python3.8/site-packages')

import spacy
import re
import joblib
import pandas as pd
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import torch
import torch.nn as nn
import pickle
import numpy as np
import inflection

# 只显示 warning 和 Error
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
   
# 注意：模型文件和知识库文件的加载路径必须要写绝对路径，否则会报错
# basic_path = '/home/xieyang/secondo/Algebras/SpatialNLQ/'
basic_path = '/home/xieyang/eclipse-workspace/nl2secondo/src/main/java/com/nl2secondo/reference/'
#basic_path = '/home/lmy/JavaDevelop/eclipse-workspace/nl2secondo/src/main/java/com/nl2secondo/reference/'

labels = ['Time Interval Query', 'Time Point Query', 'Spatial Range Query', 'Time Range Query', \
          'Spatio-temporal Range Query', 'Spatial Nearest Neighbor Query', 'Moving Objects Nearest Neighbor Query', \
          'Spatial Join Query', 'Spatio-temporal Join Query', 'Similarity Query', 'Spatial Basic-distance Query', \
          'Spatial Basic-direction Query', 'Spatial Basic-length Query', 'Spatial Basic-area Query', 'Spatial Aggregation-count Query', \
          'Spatial Aggregation-sum Query', 'Spatial Aggregation-max Query', 'Temporal Aggregation Query', 'Normal Basic Query']


# 定义LSTMCNN模型
class LSTMCNN(nn.Module):
    def __init__(self, num_embeddings, embedding_size, hidden_size, num_classes, num_filters=100, kernel_sizes=[3,4,5]):
        super(LSTMCNN, self).__init__()
        self.embedding = nn.Embedding(num_embeddings, embedding_size)
        self.lstm = nn.LSTM(input_size=embedding_size, hidden_size=hidden_size, bidirectional=True, batch_first=True)
        self.convolution_layers = nn.ModuleList([
            nn.Conv1d(in_channels=2*hidden_size, out_channels=num_filters, kernel_size=kernel_size)
            for kernel_size in kernel_sizes
        ])
        self.dropout = nn.Dropout(0.5)
        self.linear = nn.Linear(len(kernel_sizes) * num_filters, num_classes)

    def forward(self, x):
        x = self.embedding(x)
        lstm_output, (h_n, c_n) = self.lstm(x)
        x = lstm_output.permute(0, 2, 1)
        convolution_outputs = []
        for convolution in self.convolution_layers:
            convolution_output = convolution(x)
            convolution_output = nn.functional.relu(convolution_output)
            max_pool_output = nn.functional.max_pool1d(convolution_output, kernel_size=convolution_output.size(2))
            convolution_outputs.append(max_pool_output)
        concatenated_tensor = torch.cat(convolution_outputs, dim=1)
        flatten_tensor = concatenated_tensor.view(concatenated_tensor.size(0), -1)
        dropout_output = self.dropout(flatten_tensor)
        logits = self.linear(dropout_output)
        return logits

# 加载模型和相关信息
word_to_idx = torch.load(basic_path + 'save_models/word_to_idx.pth')
max_length = torch.load(basic_path + 'save_models/max_length.pth')
num_classes = len(labels)
model = LSTMCNN(len(word_to_idx), embedding_size=200, hidden_size=128, num_classes=num_classes, num_filters=200, kernel_sizes=[3,4,5])
model.load_state_dict(torch.load(basic_path + 'save_models/model.pth'))
model.eval()

def predict_type(text):
    # 将文本转换为Tensor
    vector = np.array([word_to_idx.get(word, 1) for word in text.split()] + [0]*(max_length-len(text.split())))
    vector_tensor = torch.LongTensor(vector).unsqueeze(0)
    # 对文本进行分类预测
    with torch.no_grad():
        logits = model(vector_tensor)
        predicted_class = torch.argmax(logits, dim=1).item()
    # 返回预测结果
    return labels[predicted_class]


# 以下划线开头命名，表示私有化，不希望这个变量在外部被直接调用
_known = {
    'zero': 0,
    'one': 1,
    'two': 2,
    'three': 3,
    'four': 4,
    'five': 5,
    'six': 6,
    'seven': 7,
    'eight': 8,
    'nine': 9,
    'ten': 10,
    'eleven': 11,
    'twelve': 12,
    'thirteen': 13,
    'fourteen': 14,
    'fifteen': 15,
    'sixteen': 16,
    'seventeen': 17,
    'eighteen': 18,
    'nineteen': 19,
    'twenty': 20,
    'thirty': 30,
    'forty': 40,
    'fifty': 50,
    'sixty': 60,
    'seventy': 70,
    'eighty': 80,
    'ninety': 90
}


# 英文数字变为阿拉伯数字
def spoken_word_to_number(n):
    # 将字符串 n 转为全部小写，并去除首尾空格
    n = n.lower().strip()
    if n in _known:
        return _known[n]
    else:
        # 以空格和 - 对字符串 n 进行分割，inputWordArr 为分隔之后的字符串数组
        inputWordArr = re.split('[ -]', n)
    # assert（断言）用于判断一个表达式，在表达式条件为 false 的时候触发异常
    assert len(inputWordArr) > 1  # all single words are known
    # Check the pathological case where hundred is at the end or thousand is at end
    if inputWordArr[-1] == 'hundred':
        inputWordArr.append('zero')
        inputWordArr.append('zero')
    if inputWordArr[-1] == 'thousand':
        inputWordArr.append('zero')
        inputWordArr.append('zero')
        inputWordArr.append('zero')
    if inputWordArr[0] == 'hundred':
        inputWordArr.insert(0, 'one')
    if inputWordArr[0] == 'thousand':
        inputWordArr.insert(0, 'one')
    inputWordArr = [word for word in inputWordArr if word not in ['and', 'minus', 'negative']]
    currentPosition = 'unit'
    # prevPosition = None
    output = 0
    for word in reversed(inputWordArr):
        if currentPosition == 'unit':
            number = _known[word]
            output += number
            if number > 9:
                currentPosition = 'hundred'
            else:
                currentPosition = 'ten'
        elif currentPosition == 'ten':
            if word != 'hundred':
                number = _known[word]
                if number < 10:
                    output += number * 10
                else:
                    output += number
            # else: nothing special
            currentPosition = 'hundred'
        elif currentPosition == 'hundred':
            if word not in ['hundred', 'thousand']:
                number = _known[word]
                output += number * 100
                currentPosition = 'thousand'
            elif word == 'thousand':
                currentPosition = 'thousand'
            else:
                currentPosition = 'hundred'
        elif currentPosition == 'thousand':
            assert word != 'hundred'
            if word != 'thousand':
                number = _known[word]
                output += number * 1000
        else:
            assert "Can't be here" == None
    return (output)


# 将非字母数字空符号外的所有符号替换为空格
def remove_punctuation(line):
    line = str(line)
    if line.strip() == '':
        return ''
    rule = re.compile("[^0-9a-zA-Z\s-]")
    line = rule.sub(' ', line).strip()
    return line


# 将英语单词由单数转为复数，或由复数转为单数，用于识别空间关系
def get_addi_word(word):
    result = ''
    if word.endswith("ies"):
        result = word[0:-3] + 'y'
    elif word.endswith('ses'):
        result = word[0:-2]
    elif word.endswith('s'):
        result = word[0:-1]
    elif word.endswith('y'):
        result = word[0:-1] + 'ies'
    else:
        result = word + 's'
    return result


# 返回查询近邻数
def get_neighbor_num(pos_neighbor, numbers, s):
    num_of_neighbor = 0
    if pos_neighbor != -1:
        num_of_neighbor = 1
        for i in numbers:
            pos = s.find(i)
            if pos < pos_neighbor:
                if i.isdigit():
                    num_of_neighbor = i
                else:
                    num_of_neighbor = spoken_word_to_number(i)
            # elif 只针对数字紧跟在 closest 或 nearest 后面
            elif pos == pos_neighbor + 8:
                if i.isdigit():
                    num_of_neighbor = i
                else:
                    num_of_neighbor = spoken_word_to_number(i)
    return num_of_neighbor


# 返回最大距离数，以米为单位的数字（距离join中会用到）
def get_max_distance(distance_number):
    max_distance = 0
    # 此处只考虑一个最大距离
    if len(distance_number) >= 1:
        tmpList = distance_number[0].split()
        # 考虑到浮点数的情况
        if tmpList[0].replace(".",'').isdigit():
            if "." in tmpList[0]:
                max_distance = float(tmpList[0])
            else:
                max_distance = int(tmpList[0])
        else:
            max_distance = spoken_word_to_number(tmpList[0])
        # kilometer 的 k 可能大写
        if "ilo" in tmpList[1]:
            max_distance = max_distance * 1000
    return max_distance


# 返回 noun_to_place 中相似度得分最高的元组的下标
def get_max_score(noun_to_place):
    max = noun_to_place[0][1]
    max_id = 0
    for i in range(len(noun_to_place)):
        if noun_to_place[i][1] > max:
            max = noun_to_place[i][1]
            max_id = i
    return max_id


# 提取关键语义信息：查询类型，最近邻居数，地点信息，查询关系
def get_semantic_information(s): 
    # s = s + u'am'
    # s = s+'.'
    # 将 s 中的的标点符号均替换为空格，保留连字符-，先不要都转换为小写字母，因为后续地点信息提取时要先进行完全匹配
    # s = remove_punctuation(s)
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(s)

    # 先进行查询类型预测
    # cat_info 为 Range Query、Nearest Neighbor Query、Spatial Join Query、Distance Join Query、Aggregation-count Query、Aggregation-sum Query、Aggregation-max Query
    cat_info = predict_type(s)
    # print(cat_info)

    # print("s:",s)
    # print("doc:",doc)
    # 提取查询近邻数、distance join查询中的最大距离数(此处只考虑一个最大距离)
    numbers = []
    distance_number = []
    tokenss = []
    timeconds = []
    # 上述 token 考虑的是全部词性，此处 doc.ents 只关注语句中出现的实体词汇（包括日期，时间，基数等）
    for token in doc:
        if not token.is_punct | token.is_space:
            tokenss.append(token.orth_)
    #-------update---525----
    tokens = []
    for i in range(0,len(tokenss)):
        if tokenss[i]==u'between':
            tokenss[i]=u'from'
            for j in range(i,len(tokenss)):
                if tokenss[j]!=u'and':
                    tokens.append(tokenss[j])
            break
        elif tokenss[i]==u'from':
            for j in range(i,len(tokenss)):
                if tokenss[j]!=u'to':
                    tokens.append(tokenss[j])
            break
        else:
            tokens.append(tokenss[i])
    # print("tokens:",tokens)
    ss=' '
    ss=ss.join(tokens)
    # print("join后的ss：",ss)
    doc = nlp(ss)
    for ii in doc.ents:
        # print("str(ii):",str(ii))
        # print("label:",ii.label_)
        if ii.label_ == "CARDINAL":
            numbers.append(str(ii))
        if ii.label_ == "QUANTITY":
            distance_number.append(str(ii))
        if ii.label_ == "TIME" or ii.label_ == "DATE":
            timeconds.append(str(ii))
    num_of_neighbor = 0
    pos_neighbor = s.find("nearest")
    if pos_neighbor != -1:
        num_of_neighbor = get_neighbor_num(pos_neighbor, numbers, s)
    else:
        pos_neighbor = s.find("closest")
        if pos_neighbor != -1:
            num_of_neighbor = get_neighbor_num(pos_neighbor, numbers, s)
        else:
            pos_neighbor = s.find("neighbor")
            if pos_neighbor != -1:
                num_of_neighbor = get_neighbor_num(pos_neighbor, numbers, s)

    d1 = re.compile(r'\d+.\d+')  # 正则表达式针对00：00这样格式的时间
    d2 = re.compile(r'\d+')  # 正则表达式针对单个数字格式的时间
    time = []
    if timeconds != 0:
        for j in range(0, len(timeconds)):
            temp = d1.findall(timeconds[j])
            if len(temp) != 0:
                for p in temp:
                    time.append(p)
            else:
                temp1 = d2.findall(timeconds[j])
                if len(temp1) != 0:
                    for q in temp1:
                        if (tokens.index(q) + 1) <= len(tokens) - 1:
                            if tokens[tokens.index(q) + 1] == u'pm':
                                q = str(int(q) + 12)
                            time.append(q + ':00')
    # print("time:",time)
    # print("neighbor: " + str(num_of_neighbor))
    max_distance = get_max_distance(distance_number)
    # print("max distance: " + str(max_distance))


    # words 中存放的是全部单词，noun_list 存放词性为名词的单词（包括空间关系名和地点名），noun_low 存放全部的名词小写
    words = []
    noun_low = []
    noun_list = []
    for token in doc:
        # print(token.text, token.pos_)
        if not token.is_punct | token.is_space:
            words.append(token.orth_)
            if token.pos_ == "NOUN" or token.pos_ == "PROPN":
                noun_list.append(token.text)
                noun_low.append(token.text.lower())
    # print(words)
    # print("noun_list:",noun_list)
    # print(noun_low)

    
    # 提取空间关系
    relations_file = pd.read_csv(basic_path + 'knowledge_base/spatialtemporal_relations.csv')
    # 把 'relation_name' 列的关系名全变为小写
    relations_file['lower_name'] = relations_file['name'].apply(lambda x: x.lower().strip())
    # 将 noun_low 扩充为包含单词单复数形式在内的列表
    # 其中，索引为偶数的是原 noun_low 数组中的单词
    tmp_noun = []
    for word in noun_low:
        tmp_noun.append(word)
        tmp_noun.append(get_addi_word(word))
    # print(tmp_noun)
    relations = relations_file[relations_file['lower_name'].isin(tmp_noun)]
    # print("relations:",relations)
    # spatial_relations 是一个字典数组，包含句子中存在的查询关系名称和 Geodata 类别
    spatial_relations = relations.to_dict(orient='records')
    # 添加并初始化 place 属性，同时从 noun_list 中去掉已经确定为空间关系的单词
    for relation in spatial_relations:
        relation['place'] = ''
        pos1 = tmp_noun.index(relation['lower_name'])
        # pos1 // 2，除以2向下取整，也就是这个关系名在 noun_low 和 noun_list 中的索引
        pos = pos1 // 2
        del noun_list[pos]
        # 同时也要删除 tmp_noun 中对应的两个单词，否则得到的索引可能会超出 noun_list 的长度
        # 删除第二个时请注意，第一个已经删掉了
        del tmp_noun[pos*2]
        del tmp_noun[pos*2]
    # print("spatial_relations:",spatial_relations)
    obj_id = []
    obj = [objects['name'] for objects in spatial_relations]
    obj = [word.lower() for word in obj]
    for word in obj:
        # 使用 inflection 库获取单数形式
        singular_form = inflection.singularize(word)
        # 如果单数形式和原词不同，添加到列表中
        if singular_form != word:
            obj.append(singular_form)
    for index, e in enumerate(tokens):
        if any(word in e for word in obj) and index +1 < len(tokens) and tokens[index + 1] in numbers:
        # for word in obj:
        #     if word in e and tokens[index + 1] in numbers:
            obj_id.append(tokens[index + 1])
    # print("obj:",obj)
    # print("obj_id:",obj_id)
    sorted_attr = []
    if 'than' in tokens or 'equal' in tokens or 'equals' in tokens:
        than_index = tokens.index('than')  # 找到 'than' 的索引位置
        # 确保 'than' 后面至少还有一个单词
        if than_index < len(tokens) - 1:
            # 将 'than' 后面的单词或词组添加到 sorted_attr
            sorted_attr.append(tokens[than_index + 1])
    # print(noun_list)
    # print(noun_low)
    search_for1 = "less"
    search_for2 = "more"
    search_for3 = "greater"
    search_for4 = "decreasing"
    search_for5 = "increasing"

    # 使用for循环来查找
    is_less = 0
    is_more = 0
    is_decreasing = 0
    is_increasing = 0
    for index,item in enumerate(tokens):
        if item == search_for1:
            is_less = 1
        elif item == search_for2 or item == search_for3:
            is_more = 1
        elif item == search_for4:
            is_decreasing = 1
        elif item == search_for5:
            is_increasing = 1

    # print("is_more:",is_more)
    # 提取地点信息(最多有两个地点，基础查询中有求距离和方向)
    places_file = pd.read_csv(basic_path + 'knowledge_base/places.csv')
    place_list = places_file['name'].tolist()
    # noun_to_place 存放与 noun_list 对应的地点信息，第一个用于存放完全匹配得到的结果，第二个用于存放模糊匹配得到的结果
    noun_to_place1 = []
    noun_to_place2 = []
    
    # 先进行地点信息的完全匹配
    for word in noun_list:
        if word in place_list:
            noun_to_place1.append(word)
    # print("placestest:",noun_to_place1)
    # print(len(noun_to_place1))
    # 如果地点数小于2，再进行模糊匹配
    if len(noun_to_place1) < 2:
        for word in noun_list:
            tmp = process.extractOne(word, place_list)
            if tmp[1] > 90:
                # print(tmp[0], tmp[1])
                if len(noun_to_place1) == 1 and noun_to_place1[0] != tmp[0]:
                    noun_to_place2.append(tmp)
        # print(noun_to_place2)
        # 如果 noun_to_place2 长度超过2，则取相似度得分最高的两个元组
        ll = len(noun_to_place2)
        tmp_place2 = noun_to_place2
        if ll > 2:
            first_id = get_max_score(noun_to_place2)
            first_place = noun_to_place2[first_id][0]
            del noun_to_place2[first_id]
            second_id = get_max_score(noun_to_place2)
            second_place = noun_to_place2[second_id][0]
            noun_to_place2 = []
            noun_to_place2[0] = first_place
            noun_to_place2[1] = second_place
        # 如果 noun_to_place2 长度等于2，则第一个为相似度得分最高的
        elif ll == 2:
            if noun_to_place2[0][1] < noun_to_place2[1][1]:
                first_id = 1
                second_id = 0
            else:
                first_id = 0
                second_id = 1
            noun_to_place2 = []
            noun_to_place2.append(tmp_place2[first_id][0])
            noun_to_place2.append(tmp_place2[second_id][0])
        elif ll == 1:
            noun_to_place2 = []
            noun_to_place2.append(tmp_place2[0][0])

    
    # place长度最长为2
    place = []
    if len(noun_to_place1) == 0:
        place = noun_to_place2
    elif len(noun_to_place1) == 1:
        place = noun_to_place1
        if len(noun_to_place2) > 0:
            place.append(noun_to_place2[0])
    elif len(noun_to_place1) == 2:
        place = noun_to_place1
    else:
        place[0] = noun_to_place1[0]
        place[1] = noun_to_place1[1]

    # 如果是'Basic-distance Query', 'Basic-direction Query'
    if cat_info in ['Spatial Basic-distance Query', 'Spatial Basic-direction Query']:
        # 如果不是俩地点，则会报错
        if len(place) == 2:
            t1 = places_file.loc[places_file['name'] == place[0]]['rel_id'].tolist()
            t2 = places_file.loc[places_file['name'] == place[1]]['rel_id'].tolist()
            if t1[0] > 0:
                # flag 标记 max_place 的所属关系是否存在于关系数组里，为0不存在
                flag = 0
                for relation in spatial_relations:
                    # 虽然该地点匹配到了空间关系，但是如果只有一个空间关系的话，还是要新增一个关系来存放该地点
                    if t1[0] == relation['id']:
                        if len(spatial_relations) > 1:
                            relation['place'] = place[0]
                            flag = 1
                        break
                if flag == 0:
                    add_rel = relations_file.loc[relations_file['id'] == t1[0]].to_dict(orient='records')
                    add_rel[0]['place'] = place[0]
                    spatial_relations.append(add_rel[0])
            if t2[0] > 0:
                # flag 标记 max_place 的所属关系是否存在于关系数组里，为0不存在
                flag = 0
                for relation in spatial_relations:
                    # 虽然该地点匹配到了空间关系，但是如果只有一个空间关系的话，还是要新增一个关系来存放该地点
                    if t2[0] == relation['id']:
                        if len(spatial_relations) > 1:
                            relation['place'] = place[1]
                            flag = 1
                        break
                if flag == 0:
                    add_rel = relations_file.loc[relations_file['id'] == t2[0]].to_dict(orient='records')
                    add_rel[0]['place'] = place[1]
                    spatial_relations.append(add_rel[0])
    
    # 如果是其他类型的查询，则地点最多为一个
    else:
        if len(place) > 0:
            t = places_file.loc[places_file['name'] == place[0]]['rel_id'].tolist()
            tmp_place = place[0]
            if t[0] == 0:
                place = []
                place.append(tmp_place)
            else:
                # flag 标记 max_place 的所属关系是否存在于关系数组里，为0不存在
                flag = 0
                for relation in spatial_relations:
                    # 虽然该地点匹配到了空间关系，但是如果只有一个空间关系的话，还是要新增一个关系来存放该地点
                    if t[0] == relation['id']:
                        if len(spatial_relations) > 1:
                            relation['place'] = place[0]
                            flag = 1
                        break
                if flag == 0:
                    add_rel = relations_file.loc[relations_file['id'] == t[0]].to_dict(orient='records')
                    add_rel[0]['place'] = place[0]
                    spatial_relations.append(add_rel[0])
    
    # print("query type: " + cat_info)
    # print(spatial_relations)
    # print(place)
    # print("neighbor: " + str(num_of_neighbor))
    # print("max distance: " + str(max_distance))
    # print("get_semantic_information finished!!")
    # print("sorted_attr: ", sorted_attr)
    # print("final_place:",place)
    return cat_info, spatial_relations, place, str(num_of_neighbor), str(max_distance), time, obj_id, sorted_attr,is_less, is_more, is_decreasing, is_increasing
    


# 如下直接写出的代码和写在 if __name__ == '__main__' 里面的代码主要在模块间相互引用时有所不同，如果此文件被引用，则下面代码一定会执行

# 测试 spoken_word_to_number 函数
# a = input("input: ")
# while a != '#':
    # print(spoken_word_to_number(a))
    # a = input("input: ")
    
# str1 = "What kinos are there in the TreptowerPark?"
# str1 = "Find the six closest kinos to the Advokatensteig."
# 以下两种均能识别出最大距离，注意只有符合格式 "阿拉伯数字/带有连字符的英文数字且不能有空格 + meter/kilometer" 才能识别出QUANTITY实体
# str1 = "What kinos are within one kilometer of each Flaechen?"
# str1 = "What kinos are within 25 kilometers of each Flaechen?"
# str1 = "Which rbahnhof are located in thecenter?"
# get_semantic_information(str1)
