
# Trying to understand with examples how FastAPI concurrency works

What blocks the main thread? what not? what are the differences in thread managing? memory consumption?  
All from a simple point of view.  

Infinite thanks to [@Chris](https://stackoverflow.com/users/17865804/chris) for all the answers in StackOverflow which are truly enlightening. I've used 
[this](https://stackoverflow.com/questions/77935269/performance-results-differ-between-run-in-threadpool-and-run-in-executor-in/77941425#77941425), [this](https://stackoverflow.com/questions/71516140/fastapi-runs-api-calls-in-serial-instead-of-parallel-fashion/71517830#71517830) and [this](https://stackoverflow.com/questions/70872276/fastapi-python-how-to-run-a-thread-in-the-background/70873984#70873984) extensively to grasp what's going on and I know I will read them over and over again.  

> For a quick snpashot of the results, without running anything,  you can just go to `app/main.py` and inside each function the comments will tell you the result and behaviour of each function.  
If you want to test yourself, read below.

## How to run this
The following is to create the docker image and start the API. I'm using docker so it's similar to an actual server and anyone can try and regenerate the results.  
If you don't want , you can just run in the terminal `fastapi dev main.py`  

For docker:  
`docker build -t fastapi-test .`

You can adjust the memory allocation, I wanted to test with a simple server and see crashes quickly.  
`docker run --rm -it  -p 8000:8000 --memory=512m --memory-swap=512m --cap-add=SYS_PTRACE --security-opt seccomp=unconfined --name fastapi-test fastapi-test`

## For stress testing
I am using Windows locally, so I couldn't install `hey` or other mac/linux alternatives.  
I found that because I have node installed I could use `npm install -g artillery@latest`.   
Feel free to use any service you like, this is just to quickly fire a lot of requests to the api.  

For instance, running from the terminal:  

`artillery quick --count 8 --num 2 http://localhost:8000/run_in_threadpool_memory`

## Usage

### Blocking or not.
What I did was to build and run the Docker image explained above.  

Then for basic testing, you can just go to `localhost:8000/docs` in your browser and manually  triggering any endpoint you want to test if it blocks or not. While it spins, you can click the root one that just returns "hello world". If it returns inmediately, the api is not blocked as it is the simplest possible endpoint. If it waits until the other endpoint finishes, it's blocked.  

You can of course do it with scripts or from the terminal with `curl` or any way to hit the endpoints.  

In the terminal, as we have the profiler running, you will be able to see the rss_mb (memory from the api), cpu usage and the threads count, etc.    

If you are using docker, you can go to "stats" in Docker Desktop (windows!, not sure in other OS how that's seen) and check also a timeline of cpu and memory consumption. It's important too because there you can see the OS total memory consumption and not only the API one. Sometimes they differ. API could be "free" but the OS still using a lot somehow.  

### Stress testing
Use as you need for your use case but what I wanted to do was to see how the OS and API memory was freed (or not!) as I called the memory intensive endpoints repeteadly.  You will see that is not always obvious the behaviour with Python and progressive calls can keep stacking memory despite the function having finished running and eventually you could hit OOM!.  

What I did was for instance:   
`artillery quick --count 8 --num 2 http://localhost:8000/run_in_threadpool_memory`

and play around with the count number, run it multiple times, etc.  
I still need to re do these experiments and track properly.
