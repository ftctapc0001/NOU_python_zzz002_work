import csv
import os
import params
from MySQL import MySQL
class CreateLvrData:

    def getCsv(self, path, fileType, cityCode):
        '''
        讀取一個csv檔案，使用encoding='utf-8-sig'配置可以在檔頭有BOM時過濾掉
        Args:
            path: (string) 檔案路徑
        '''
        cityCode = cityCode.upper()
        with open(path, mode='r', encoding='utf-8-sig') as file:
            # mapping表
            map = {
                "鄉鎮市區": "town_name", 
                "交易標的": "trade_sign", 
                "土地位置建物門牌": "address", 
                "交易年月日": "trade_date", 
                "總價元": "price_total", 
                "單價元平方公尺": "price_nuit", 
                "建物移轉總面積平方公尺": "total_area",
                "編號": "code", 
                "屋齡": "age"
            }
            # 交易標地
            tradeMap = {
                "":0,
                "房地(土地+建物)": 1,
                "建物": 2,
                "土地": 3,
                "車位": 4,
                "房地(土地+建物)+車位": 5
            }
            # 使用字典方式讀取csv
            csv_reader = csv.DictReader(file)
            # 要返回的列表
            data = []
            for i, d in enumerate(csv_reader):
                # 檔案第一行跳過（檔頭不需要）
                if i == 0:
                    continue
                
                # 取得在map字典中有對應的key產生出新的字典
                result = {}
                for key, value in d.items():
                    if(key in map):
                        if map[key] == 'age':
                            result[map[key]] = (int(value) if value.isdigit() else 0)
                        elif map[key] == 'trade_sign':
                            result[map[key]] = tradeMap.get(value, 0)
                        elif map[key] == 'price_nuit':
                            result[map[key]] = (int(value) if value.isdigit() else 0)
                        else:
                            result[map[key]] = value
                
                # 單行寫法（不好閱讀）
                #result = {map[key]: (0 if map[key] == 'age' and len(value) == 0 else int(value) if map[key] == 'age' else value) for key, value in d.items() if key in map}
                
                # 如果是主檔，添加縣市與鄉鎮市相關資訊
                if fileType == 'main':
                    result = {
                        'city_code': cityCode,
                        'city_name': params.city[cityCode],
                        'town_code': next((item["code"] for item in params.town[cityCode] if item["title"] == result["town_name"]), None),
                        'age': 0
                    } | result
                    
                _k = len(data)
                data.append(_k)
                data[_k] = result
            return data

    def getData(self, outputModel = 1, rows = -1):
        '''
        從opendata資料夾中取得對應的csv檔數據，
        發現a_lvr_land_b.csv後面為_b的檔案類型，因該是土地+車位，因該也可以略過不抓
        Args:
            outputModel: (int) 0 => 輸出字典模式 e.g {A:[],B:[]} 1 => 串列模式 e.g. [{item1...},{item2...}]
        '''
        # 取當前目錄
        currentDir = os.path.dirname(os.path.abspath(__file__))
        # opendata目錄
        openddataDir = os.path.join(currentDir, '..', 'opendata')
        # 取所有子目錄列表（這種寫的問題是在萬一參雜了非需要的資料目錄可能會在讀取csv時出錯）
        dirList = [os.path.join(openddataDir, d) for d in os.listdir(openddataDir) if os.path.isdir(os.path.join(openddataDir, d))]
        # 儲存最終結果的列表
        if outputModel == 1:
            result = []
        else:
            result = {}
        # 迴圈所有的data資料夾
        for index, dirPath in enumerate(dirList):
            if index == rows:
                break 
            # 處理檔案中的a-z開頭
            for fi, i in enumerate(range(ord('a'), ord('z') + 1)):
                if fi == rows:
                    break 
                key = chr(i)
                # 如果需要抓其他後綴檔案 像是xxx_b.csv _c.csv，可以在多一曾回圈先處理檔案命稱
                # for prefix in ["a", "b", "c"]:
                #   fileList = [f"{key}_lvr_land_{prefix}_{suffix}.csv" for suffix in ['build', 'land', 'park']]
                #   fileList.insert(0, f"{key}_lvr_land_{prefix}.csv")
                # ... 後面的邏輯就都差不多
                try:
                    # 後來對照比對後，發現_b的檔案是土地＋車位資料，也可略過不抓
                    prefix = os.path.join(dirPath, f"{key}_lvr_land_a")
                    fileList = [f"{prefix}_{suffix}.csv" for suffix in ['build', 'land', 'park']]
                    fileList.insert(0, f"{prefix}.csv")
                    # 取檔案內容
                    print(f"處理檔案：{fileList[0]}")
                    main = self.getCsv(fileList[0], 'main', key) if os.path.exists(fileList[0]) else None
                    build = self.getCsv(fileList[1], 'build', key) if os.path.exists(fileList[1]) else None
                    
                    # 沒有檔案的話就跳過
                    if main == None:
                        continue
                    # 把build轉換把code(編號)作為key
                    build_dict = {item["code"]: item["age"] for item in build} if build != None else {}
                    
                    # 取的對應的屋齡
                    for item in main:
                        code = build_dict.get(item['code'], 0)
                        item['age'] = code

                    # 將資料加入到輸出結果
                    if outputModel == 1:
                        result.extend(main)
                    else:
                        if key.upper() in result:
                            result[key.upper()].extend(main)
                        else:
                            result[key.upper()] = main
                except ValueError as e:
                    print(f"檔案：{fileList[0]}, 發生異常{e}")
                except Exception as e:
                    print(f"檔案：{fileList[0]}, 發生異常{e}")
        return result

    def insertSQL(self, row = 1000):
        '''
        將數據寫入資料庫每1000比進行一次批次寫入
        '''
        print("資料庫已完成上傳，請勿重複執行")
        return
        result = self.getData(1)
        total = len(result)
        print(f"共有{total // row + 1}批資料要寫入每批資料有{row}筆")
        with MySQL.MySQL() as db:
            sql = []
            sql.append("INSERT INTO omeiliau_nou.lvr_lnd (city_code, city_name, town_code, town_name, trade_sign, address, trade_date, price_total, price_nuit, total_area, code, age)")
            sql.append(f"VALUES ({(", ".join(["%s"] * 12))})")
            data_to_insert = []
            for idx,item in enumerate(result):
                #將字典轉元組
                data_to_insert.append((item["city_code"],item["city_name"],item["town_code"],item["town_name"],item["trade_sign"],item["address"],item["trade_date"],item["price_total"],item["price_nuit"],item["total_area"],item["code"],item["age"]))
                # db.insert_many(" ".join(sql), data_to_insert)
                if len(data_to_insert) >= row or idx == total - 1:
                    db.insert_many(" ".join(sql), data_to_insert)
                    data_to_insert = []  # 清空資料，為下一批次做準備
                    print(f"已批次寫入資料：第 {idx // row + 1} 批")