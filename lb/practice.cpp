#include <iostream>
#include <stack>
#include <string>
#include <vector>
#include <unordered_set>

using namespace std;

vector<vector<int>> allPathsSourceTarget(vector<vector<int>>& graph) {
        
        vector<vector<int>> paths;
        stack<vector<int>> stack;
        stack.push(vector<int>{0});
        unordered_set<int> seen;
    
        while (!stack.empty()){
            int len=stack.size();
            while (len>0) {
                vector<int> top_path=stack.top();
                stack.pop();
                cout << top_path[top_path.size()-1] << endl;
                vector<int> tmp(top_path.size());
                copy(top_path.begin(),top_path.begin()+top_path.size(),tmp.begin());
                if (top_path[top_path.size()-1]==graph.size()-1)
                    paths.push_back(tmp);
                int last_node_top_path=top_path[top_path.size()-1];
                for (int i=0;i<graph[last_node_top_path].size();i++){
                        tmp.push_back(graph[last_node_top_path][i]);
                        stack.push(tmp);
                    }
                len--;
                    
                }
                
            }
        return paths;
        }

int main(){
    vector<vector<int>> input={{1,2},{3},{3},{}};
    vector<vector<int>> paths=allPathsSourceTarget(input);
    for (auto& path: paths){
        for (auto& node: path){
            cout << node << " " << endl;
        }
        cout << "\n" << endl;
    }
}