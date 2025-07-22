#include "Algebra.h"
#include "NestedList.h"
#include "QueryProcessor.h"
#include "StandardTypes.h"
#include "Algebras/FText/FTextAlgebra.h"
#include <iostream>
#include <string>
#include <cstring> 
#include <map>
// 调用 python 模块需要的头文件
#include "/home/xieyang/anaconda3/include/python3.8/Python.h"

extern NestedList     *nl;
extern QueryProcessor *qp;
// 输入的自然语言查询的最大字符数
const int MaxCharNum=500;
PyObject* pModule3;

using namespace std;

/****************************************************************

operator NL4ST

***************************************************************/
ListExpr NL4STTypeMap( ListExpr args )
{
	//error message;
    string msg = "string expected";
	// check the number of arguments
    if( nl->ListLength(args) != 1){
        ErrorReporter::ReportError(msg + " (invalid number of arguments)");//无效的参数目
        return nl->TypeError();
    }
    // check type of the argument
    ListExpr question = nl->First(args);
    if(nl->SymbolValue(question) != "string"){
        ErrorReporter::ReportError(msg + " (first args is not a string)");
        return listutils::typeError();
    }
    // return the result type: nl->SymbolAtom(CcString::BasicType());
    return NList(FText::BasicType()).listExpr();
}

//把const char *c转 wchar_t * ，作为Py_SetPythonHome()参数匹配
 wchar_t *GetWC3(const char *c)
{
    const size_t cSize = strlen(c) + 1;
    wchar_t* wc = new wchar_t[cSize];
    mbstowcs(wc, c, cSize);
    return wc;
}

int NL4STValueMap(Word *args, Word &result, int message, Word &local, Supplier s)
{
    char a[MaxCharNum];
    string nl = ((CcString*)args[0].addr)->GetValue();
    strcpy(a,nl.c_str());
    cout<<"****************************"<<endl;
    cout<<"NLQ: "<<nl<<endl;
    
    // cout<<"开始运行 python：\n";
    // 初始化
    Py_SetPythonHome(GetWC3("/home/xieyang/anaconda3"));
    Py_Initialize();
    // PyRun_SimpleString("print('hello!')");
	
    // 将Python工作路径切换到待调用模块所在目录，一定要保证路径名的正确性
    string path = "/home/xieyang/secondo/Algebras/NL4ST";
    string chdir_cmd = string("sys.path.append(\"") + path + "\")";
    const char* cstr_cmd = chdir_cmd.c_str();
    PyRun_SimpleString("import sys");
    PyRun_SimpleString(cstr_cmd);
    
    // 加载模块
    pModule3 = PyImport_ImportModule("NLG");
    if (!pModule3) // 加载模块失败
    {
        cout<<"[ERROR] Python get module failed."<<endl;
        return 0;
    }
    cout<<"[INFO] Python get module succeed."<<endl;
    
    // 加载函数
    PyObject* pv = PyObject_GetAttrString(pModule3, "secondo");
    if (!pv || !PyCallable_Check(pv))  // 验证是否加载成功
    {
        cout<<"[ERROR] Can't find funftion (secondo)"<<endl;
        return 0;
    }
    cout<<"[INFO] Get function (secondo) succeed."<<endl;
    
    // 设置参数
    PyObject* pArgs = PyTuple_New(1);   // 1个参数
    // i表示创建int型变量，s表示创建字符串
    PyTuple_SetItem(pArgs, 0, Py_BuildValue("s", a));
	
    // 调用函数
    PyObject* pRet = PyObject_CallObject(pv, pArgs);

    // python2中才有PyString_AsString
    // nlresult 中存放的是转换结果
    string nlresult = PyUnicode_AsUTF8(pRet);
	
    cout<<"****************************"<<endl;
    
    result = qp->ResultStorage(s);
    FText* res = (FText*)(result.addr);
    res->Set(true,nlresult);
    
    return 0;
}

struct INLASTInfo : OperatorInfo {
    INLASTInfo()
    {
        name = "INLAST";
        signature = "string -> string";
        syntax = "INLAST( )";
        meaning = "Natural language to structured language";
    }
};


/****************************************************************

Algebra Monitor

***************************************************************/
class INLASTAlgebra : public Algebra
{
public:
	INLASTAlgebra() : Algebra()
	{
		AddOperator(INLASTInfo(), INLASTValueMap, INLASTTypeMap);
	}

	~INLASTAlgebra() {
		// 释放资源
		Py_Finalize();
	}
};



// Initialization of the Algebra
extern "C"
Algebra* InitializeINLASTAlgebra(NestedList *nlRef, QueryProcessor *qpRef)
{
	nl = nlRef;
	qp = qpRef;
	return (new INLASTAlgebra());
}
