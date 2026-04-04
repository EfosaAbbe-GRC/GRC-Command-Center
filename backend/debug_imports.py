try:
    from langchain.chains import RetrievalQA
    print("Found in langchain.chains")
except ImportError:
    print("Not in langchain.chains")

try:
    from langchain_community.chains import RetrievalQA
    print("Found in langchain_community.chains")
except ImportError:
    print("Not in langchain_community.chains")
