#ifndef REQUEST_CPP
#include "request.cpp"
#endif

class websrv{
    public:
        websrv() {
            requestStartTime=0;
            strcpy(serverName, "Web");
            
        }
        websrv(char name[]) {
            requestStartTime=0;
            strcpy(serverName, name);
            
        }
        void addRequest(request req, int currTime) {
            this->req=req;
            requestStartTime=currTime;
        }
        request getRequest() {
            return this->req;
        }

        char* getName(){
            return this->serverName;
        }

        bool isRequestDone(int currTime){
            if (currTime > (requestStartTime + req.time_to_process))
                return true;
        }
    private:
        request req;
        int requestStartTime;
        char serverName[10];
};