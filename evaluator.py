from typing import Any
import Levenshtein as ls
import os
import math
 
"""
AC 自动机 这里使用模糊关键字进行匹配获取对应位置
"""
class Automation(object):
    def __init__(self, keywords_dict:list):
        self.root = Node()
        self.keywords = []
        self.apply_dict(keywords_dict)
        
    def __call__(self, content) -> list:
        return self.search(content)
 
    def add_keyword(self, word):
        """
        添加匹配关键字
        """
        self.keywords.append(word)
        temp_root = self.root
        for char in word:
            if char not in temp_root.next:
                temp_root.next[char] = Node()
            temp_root = temp_root.next[char]
        temp_root.isWord = True
        temp_root.word = word
 
    def apply_dict(self,keywords_dict):
        """
        读取字典内的关键字
        """
        for word in keywords_dict:
            self.add_keyword(word)
 
    def make_fail(self):
        """
        定位fail指针
        """
        temp_que = []
        temp_que.append(self.root)
        while len(temp_que) != 0:
            temp = temp_que.pop(0)
            p = None
            for key,value in temp.next.item():
                if temp == self.root:
                    temp.next[key].fail = self.root
                else:
                    p = temp.fail
                    while p is not None:
                        if key in p.next:
                            temp.next[key].fail = p.fail
                            break
                        p = p.fail
                    if p is None:
                        temp.next[key].fail = self.root
                temp_que.append(temp.next[key])
 
 
    def search(self, content):
        p = self.root
        result = set()
        index = 0
        while index < len(content) - 1:
            currentposition = index
            while currentposition < len(content):
                word = content[currentposition]
                while word in p.next == False and p != self.root:
                    p = p.fail
 
                if word in p.next:
                    p = p.next[word]
                else:
                    p = self.root
 
                if p.isWord:
                    end_index = currentposition + 1
                    result.add((p.word, end_index - len(p.word), end_index))
                    break
                currentposition += 1
            p = self.root
            index += 1
        return list(result)
 
"""
AC 自动机辅助节点
"""
class Node(object):
    def __init__(self):
        self.next = {}
        self.fail = None
        self.isWord = False
        self.word = "" 

"""
评估器 用于评估句子含有关键词的总体莱文斯坦比
"""
class Evaluator():
    def __init__(self,eva_config:dict) -> None:
        self.keywords_dict_path = eva_config['keywords_dict_path']
        self.keywords_threshold = eva_config['threshold_keyword_recognition']
        self.use_max_probability = eva_config['use_max_probability']
        
        self.keychars = []
        self.keywords = []
        
        self.debug = False
        
        with open(eva_config['keywords_dict_path'],"r",encoding="utf-8") as file:
            for line in file:
                self.keychars.append(line.strip())
            file.close()
            
        unique_char_set = set()
        for char in ''.join(self.keychars):
            unique_char_set.add(char)
        self.keywords = list(unique_char_set)
        
        self.ac = Automation(self.keywords)
                
    def __call__(self,content) -> float:
        return self.evaluate(content)
    
    def evaluate(self,content) -> float:
        keywords = set()
        ac_res = self.ac.search(content)
        
        if self.debug:
            print(f"Full Sentence : {content}")
            print(f"Ac Res : {ac_res}")
        step = 0
        
        sum_ls_ratio = 0
        sum_jaro_winkler = 0
        max_probability = 0
        
        for datas in ac_res:
            fuzzy_keyword = datas[0]

            for exact_keyword in self.keychars:
                start = datas[1]
                end = datas[2]
                
                fuzzy_index = exact_keyword.find(fuzzy_keyword)
                if fuzzy_index != -1:
                    step += 1
                    start = max(0,start-int(fuzzy_index))
                    end = min(len(content),end+int(len(exact_keyword)-fuzzy_index-1))

                    ls_ratio = ls.ratio(content[start:end],exact_keyword)
                    jaro_winkler = ls.jaro_winkler(content[start:end],exact_keyword)
                    
                    sum_ls_ratio += ls_ratio
                    sum_jaro_winkler += jaro_winkler
                    
                    # 保存80%匹配的关键字
                    temp_sum_probability = (ls_ratio + jaro_winkler) / 2
                    if temp_sum_probability >= self.keywords_threshold:
                        keywords.add(exact_keyword)
                        
                        if temp_sum_probability > max_probability: # 获取精确关键字匹配的最大概率
                            max_probability = temp_sum_probability

                    if self.debug:
                        print(f'{fuzzy_keyword}{ac_res.index(datas)}|{exact_keyword} -> {content[start:end]} [{start}:{end}] -> {round(ls_ratio*100,2)}% | {round(jaro_winkler*100,2)}% => Max:{round(max_probability*100,2)}%')

        if step == 0:
            return 0,[]
        
        probability = (sum_jaro_winkler + sum_ls_ratio) / (2 * step)

        if self.debug:
            # 如果对关键词敏感 后面之间使用max_probability即可
            print(f'Probability:{round(probability,2)} Max_Probability：{round(max_probability,2)}')
            
        return round(max_probability,2) if self.use_max_probability else round(probability,2),list(keywords)
    
if __name__ == "__main__":
    sen1 = "我今天打了个饭，阿姨跟我说别点那个三鲜米线，麻的疼人,整的我打电话给室友喊救命了"
    sen2 = "求求你，别打我了，好疼，救命"
    
    from config import config
    
    e = Evaluator(eva_config = config.eva_config)
    e.debug = True
    res,kw = e(sen1)  
    print(f"Probability : {res}\n{kw}")
    res,kw = e(sen2)  
    print(f"Probability : {res}\n{kw}")