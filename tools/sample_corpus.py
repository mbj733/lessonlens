"""The evaluation corpus: ten self-authored 10-slide decks (5 English, 5 Chinese).

Everything here is written from standard textbook definitions, so the repository ships no
third-party slide content. The decks are the *only* input the pipeline is evaluated on, which
keeps the numbers reproducible and the licensing trivial.

Each slide is ``{"title": str, "bullets": [str, ...]}`` or ``{"title": str, "table": {...}}``.
Page index == slide index == PDF page number, so a claim's ``page`` field is meaningful in
every output format.
"""

from __future__ import annotations

DECKS: list[dict] = [
    {
        "id": "en-01-sorting",
        "lang": "en",
        "title": "Sorting Algorithms",
        "subtitle": "CS 201 · Algorithms · Lecture 4",
        "slides": [
            {
                "title": "The Sorting Problem",
                "bullets": [
                    "Given n comparable keys, produce a permutation in non-decreasing order.",
                    "A comparison sort may only inspect keys through pairwise comparisons.",
                    "A stable sort keeps equal keys in their original relative order.",
                ],
            },
            {
                "title": "Comparison Lower Bound",
                "bullets": [
                    "Any comparison sort needs Ω(n log n) comparisons in the worst case.",
                    "The decision tree has n! leaves, so its height is at least log2(n!).",
                    "Stirling's approximation gives log2(n!) = Θ(n log n).",
                ],
            },
            {
                "title": "Merge Sort",
                "bullets": [
                    "Split the array in half, sort each half recursively, then merge.",
                    "The recurrence T(n) = 2T(n/2) + Θ(n) solves to Θ(n log n).",
                    "It is stable but needs Θ(n) auxiliary space.",
                ],
            },
            {
                "title": "Quick Sort",
                "bullets": [
                    "Partition around a pivot, then sort the two sides independently.",
                    "Average Θ(n log n); worst case Θ(n^2) when the pivot is always extreme.",
                    "In place apart from the recursion stack, but not stable.",
                ],
            },
            {
                "title": "Heap Sort",
                "bullets": [
                    "Build a max-heap in Θ(n), then repeatedly extract the maximum.",
                    "Θ(n log n) in the worst case and in place.",
                    "Not stable, and its cache behaviour is worse than quick sort in practice.",
                ],
            },
            {
                "title": "Insertion Sort",
                "bullets": [
                    "Repeatedly take the next key and shift larger keys one slot to the right.",
                    "Θ(n^2) in the worst case but Θ(n) on nearly sorted input.",
                    "Stable and in place, which is why hybrid sorts use it for small runs.",
                ],
            },
            {
                "title": "Complexity Table",
                "table": {
                    "header": ["Algorithm", "Average", "Worst", "Space", "Stable"],
                    "rows": [
                        ["Merge sort", "Θ(n log n)", "Θ(n log n)", "Θ(n)", "Yes"],
                        ["Quick sort", "Θ(n log n)", "Θ(n^2)", "Θ(log n)", "No"],
                        ["Heap sort", "Θ(n log n)", "Θ(n log n)", "Θ(1)", "No"],
                        ["Insertion sort", "Θ(n^2)", "Θ(n^2)", "Θ(1)", "Yes"],
                    ],
                },
            },
            {
                "title": "Linear-Time Sorts",
                "bullets": [
                    "Counting sort runs in Θ(n + k) when keys are integers in [0, k).",
                    "Radix sort sorts digit by digit from the least significant position.",
                    "Both are non-comparison sorts, so the Ω(n log n) bound does not apply.",
                ],
            },
            {
                "title": "Choosing a Sort",
                "bullets": [
                    "Nearly sorted input: insertion sort is close to Θ(n).",
                    "External sorting on disk: merge sort minimises sequential I/O.",
                    "Hard real-time guarantees: heap sort avoids the quadratic worst case.",
                ],
            },
            {
                "title": "Summary",
                "bullets": [
                    "Comparison sorts cannot beat Ω(n log n) in the worst case.",
                    "Merge sort trades memory for stability and predictable time.",
                    "Quick sort is usually fastest but must guard against bad pivots.",
                ],
            },
        ],
    },
    {
        "id": "en-02-bst",
        "lang": "en",
        "title": "Binary Search Trees",
        "subtitle": "CS 201 · Data Structures · Lecture 6",
        "slides": [
            {
                "title": "Definition",
                "bullets": [
                    "A BST is a binary tree where every node's left subtree holds smaller keys and its right subtree holds larger keys.",
                    "Duplicates are excluded, or handled by one documented rule.",
                    "The ordering invariant holds recursively at every node.",
                ],
            },
            {
                "title": "Search",
                "bullets": [
                    "Compare the target with the root: go left if smaller, right if larger.",
                    "The cost is Θ(h), where h is the height of the tree.",
                    "A balanced tree has h = Θ(log n); a degenerate chain has h = n.",
                ],
            },
            {
                "title": "Insertion",
                "bullets": [
                    "Search for the key until a null child is reached, then attach a new leaf.",
                    "Insertion never restructures an existing node.",
                    "The running time equals the search time, Θ(h).",
                ],
            },
            {
                "title": "Deletion",
                "bullets": [
                    "A leaf is removed directly.",
                    "A node with one child is replaced by that child.",
                    "A node with two children is replaced by its in-order successor, then that node is deleted.",
                ],
            },
            {
                "title": "Traversals",
                "bullets": [
                    "Pre-order visits node, left, right; in-order visits left, node, right; post-order visits left, right, node.",
                    "In-order traversal of a BST yields keys in sorted order.",
                    "Each traversal costs Θ(n) time and Θ(h) stack space.",
                ],
            },
            {
                "title": "Balanced Variants",
                "bullets": [
                    "AVL trees keep the height difference between siblings at most 1 using rotations.",
                    "Red-black trees relax that rule but guarantee h <= 2 log2(n + 1).",
                    "C++ std::map and Java TreeMap are red-black trees.",
                ],
            },
            {
                "title": "Building a Balanced Tree",
                "bullets": [
                    "Sort the keys, then take the middle element as the root of each subtree.",
                    "This builds a height-balanced BST in Θ(n log n), dominated by the sort.",
                    "Inserting pre-sorted keys into a plain BST produces a chain, so balance first.",
                ],
            },
            {
                "title": "Cost Summary",
                "table": {
                    "header": ["Operation", "Unbalanced", "Balanced", "Note"],
                    "rows": [
                        ["Search", "O(n)", "O(log n)", "h is the only variable"],
                        ["Insert", "O(n)", "O(log n)", "plus rotations"],
                        ["Delete", "O(n)", "O(log n)", "successor swap"],
                        ["In-order walk", "O(n)", "O(n)", "sorted output"],
                    ],
                },
            },
            {
                "title": "Why Not a Sorted Array",
                "bullets": [
                    "A sorted array searches in O(log n) but inserts in O(n) because of shifting.",
                    "A BST keeps both operations logarithmic when it stays balanced.",
                    "Cache locality still favours arrays for read-only workloads.",
                ],
            },
            {
                "title": "Summary",
                "bullets": [
                    "The BST invariant turns search into a guided path.",
                    "Height is the only performance variable: balance it or pay Θ(n).",
                    "In-order traversal is why BSTs support ordered iteration.",
                ],
            },
        ],
    },
    {
        "id": "en-03-hashing",
        "lang": "en",
        "title": "Hash Tables",
        "subtitle": "CS 201 · Data Structures · Lecture 8",
        "slides": [
            {
                "title": "Core Idea",
                "bullets": [
                    "A hash function maps a key to an index in an array of m buckets.",
                    "Lookup, insertion and deletion are O(1) in expectation while the table is not too full.",
                    "The hash function must be deterministic and spread keys evenly.",
                ],
            },
            {
                "title": "Load Factor",
                "bullets": [
                    "Load factor α = n / m, where n keys are stored in m buckets.",
                    "Chaining stays fast while α is below about 1; open addressing wants α below 0.7.",
                    "When α exceeds the threshold, rehash into a table roughly twice as large.",
                ],
            },
            {
                "title": "Collision Resolution: Chaining",
                "bullets": [
                    "Each bucket stores a list of all keys mapped to it.",
                    "The average search cost is Θ(1 + α).",
                    "Java's HashMap converts a long chain into a red-black tree once it exceeds 8 entries.",
                ],
            },
            {
                "title": "Collision Resolution: Open Addressing",
                "bullets": [
                    "On collision, probe the next free slot instead of allocating a node.",
                    "Linear probing is cache friendly but suffers from primary clustering.",
                    "Deletion needs tombstones, because an emptied slot must not break a probe sequence.",
                ],
            },
            {
                "title": "Hash Functions",
                "bullets": [
                    "Division method: h(k) = k mod m, with m preferably prime.",
                    "Multiplication method: multiply by a constant in (0, 1) and take the fractional part.",
                    "Python randomises string hashing per process to defeat hash-flooding attacks.",
                ],
            },
            {
                "title": "Operation Costs",
                "table": {
                    "header": ["Operation", "Average", "Worst", "Note"],
                    "rows": [
                        ["Search", "Θ(1)", "Θ(n)", "all keys collide"],
                        ["Insert", "Θ(1)", "Θ(n)", "may trigger a rehash"],
                        ["Delete", "Θ(1)", "Θ(n)", "tombstones"],
                        ["Iterate", "Θ(n + m)", "Θ(n + m)", "visits empty buckets"],
                    ],
                },
            },
            {
                "title": "Applications",
                "bullets": [
                    "Symbol tables in compilers and interpreters.",
                    "Set membership, plus Bloom filters when an approximate answer is enough.",
                    "Caches combine hashing with an eviction policy such as LRU.",
                ],
            },
            {
                "title": "Common Mistakes",
                "bullets": [
                    "Using a mutable object as a key breaks the invariant once it is mutated.",
                    "Assuming O(1) worst case: adversarial keys can force Θ(n) per operation.",
                    "Forgetting that iteration order is arbitrary, which makes output unstable between runs.",
                ],
            },
            {
                "title": "Choosing a Strategy",
                "bullets": [
                    "Chaining is simpler to delete from and tolerates high load factors.",
                    "Open addressing is faster when the table fits in cache and keys are small.",
                    "Untrusted input requires a keyed hash such as SipHash, not a plain polynomial hash.",
                ],
            },
            {
                "title": "Summary",
                "bullets": [
                    "Hashing turns a search problem into an indexing problem.",
                    "Collision handling and load factor decide the real constant factors.",
                    "The worst case stays linear, so untrusted input needs keyed hashing.",
                ],
            },
        ],
    },
    {
        "id": "en-04-shortest-paths",
        "lang": "en",
        "title": "Shortest Paths in Graphs",
        "subtitle": "CS 202 · Algorithms · Lecture 9",
        "slides": [
            {
                "title": "Problem Statement",
                "bullets": [
                    "Given a weighted graph, find the minimum-cost path from a source s to every vertex.",
                    "The cost of a path is the sum of its edge weights.",
                    "A distance is infinite when the vertex is unreachable.",
                ],
            },
            {
                "title": "Breadth-First Search",
                "bullets": [
                    "BFS explores vertices in order of hop count.",
                    "On an unweighted graph it computes shortest paths in O(V + E).",
                    "It needs a FIFO queue and a visited set.",
                ],
            },
            {
                "title": "Dijkstra: Idea",
                "bullets": [
                    "Keep a tentative distance for every vertex: 0 for the source, infinity elsewhere.",
                    "Repeatedly extract the unvisited vertex with the smallest tentative distance and relax its edges.",
                    "It is correct only when all edge weights are non-negative.",
                ],
            },
            {
                "title": "Dijkstra: Complexity",
                "bullets": [
                    "With a binary heap the running time is O((V + E) log V).",
                    "With a Fibonacci heap it becomes O(E + V log V).",
                    "The relaxation code is identical regardless of the priority queue.",
                ],
            },
            {
                "title": "Negative Edges",
                "bullets": [
                    "Dijkstra may finalise a vertex too early when a negative edge exists.",
                    "Bellman-Ford relaxes every edge V - 1 times and runs in O(V E).",
                    "Bellman-Ford also detects negative cycles: one more successful relaxation proves the answer is undefined.",
                ],
            },
            {
                "title": "All-Pairs Shortest Paths",
                "bullets": [
                    "Running Dijkstra from every source costs O(V (V + E) log V).",
                    "Floyd-Warshall runs in Θ(V^3) and tolerates negative edges without negative cycles.",
                    "Johnson's algorithm reweights the graph, then runs Dijkstra once per source.",
                ],
            },
            {
                "title": "A* Search",
                "bullets": [
                    "A* orders the queue by f(v) = g(v) + h(v): cost so far plus an estimate to the goal.",
                    "The heuristic must be admissible, meaning it never overestimates the remaining cost.",
                    "With a consistent heuristic, A* never needs to reopen a closed vertex.",
                ],
            },
            {
                "title": "Practical Notes",
                "bullets": [
                    "Sparse road networks use Dijkstra with a 4-ary heap plus bidirectional search.",
                    "Contraction hierarchies precompute shortcuts and answer continental queries in microseconds.",
                    "Distances are stored in a hash map keyed by vertex id, because real graphs are huge.",
                ],
            },
            {
                "title": "Choosing the Algorithm",
                "bullets": [
                    "Unweighted graph: BFS.",
                    "Non-negative weights: Dijkstra.",
                    "Negative weights: Bellman-Ford, or Johnson for all pairs.",
                ],
            },
            {
                "title": "Summary",
                "bullets": [
                    "BFS for unweighted graphs, Dijkstra for non-negative weights, Bellman-Ford when edges can be negative.",
                    "The priority queue dominates the running time.",
                    "An admissible heuristic turns a blind search into a guided one.",
                ],
            },
        ],
    },
    {
        "id": "en-05-processes-threads",
        "lang": "en",
        "title": "Processes and Threads",
        "subtitle": "CS 210 · Operating Systems · Lecture 3",
        "slides": [
            {
                "title": "Process",
                "bullets": [
                    "A process is a program in execution with its own virtual address space.",
                    "It owns a page table, file descriptors, signal handlers and at least one thread.",
                    "Processes are isolated: one crash cannot corrupt another process's memory.",
                ],
            },
            {
                "title": "Thread",
                "bullets": [
                    "A thread is a schedulable execution context inside a process.",
                    "Threads of one process share code, data and open files, but not registers or stack.",
                    "Sharing makes communication cheap and data races possible.",
                ],
            },
            {
                "title": "Context Switch",
                "bullets": [
                    "The kernel saves registers and the program counter, then restores the next context.",
                    "A thread switch inside one process avoids changing the address space.",
                    "A process switch also invalidates TLB entries and swaps page tables, so it costs more.",
                ],
            },
            {
                "title": "Inter-Process Communication",
                "bullets": [
                    "Pipes and FIFOs move a byte stream between related processes.",
                    "Shared memory is the fastest form of IPC but requires explicit synchronisation.",
                    "Sockets generalise IPC across machines, while message queues decouple timing.",
                ],
            },
            {
                "title": "Scheduling",
                "bullets": [
                    "The scheduler picks a runnable thread by policy: round robin, priority or fair share.",
                    "Preemption uses a timer interrupt to guarantee responsiveness.",
                    "Blocking I/O moves a thread to the waiting state and yields the CPU.",
                ],
            },
            {
                "title": "Synchronisation",
                "bullets": [
                    "A mutex protects a critical section: only one thread enters at a time.",
                    "A semaphore counts resources and may be signalled from a different thread.",
                    "Condition variables let a thread sleep until a predicate becomes true.",
                ],
            },
            {
                "title": "Deadlock",
                "bullets": [
                    "Deadlock needs mutual exclusion, hold and wait, no preemption and circular wait.",
                    "Breaking any one of the four conditions prevents it entirely.",
                    "Lock ordering and timeouts are the usual practical defences.",
                ],
            },
            {
                "title": "Comparing Costs",
                "bullets": [
                    "Creating a thread is cheaper than forking a process because nothing is copied.",
                    "Python's GIL serialises bytecode execution, so threads help with I/O but not CPU-bound work.",
                    "Processes buy isolation and CPU parallelism, threads buy shared-state concurrency.",
                ],
            },
            {
                "title": "Design Checklist",
                "bullets": [
                    "Write down what state is shared before choosing between a process and a thread.",
                    "Prefer immutable messages over shared mutable memory when the cost allows it.",
                    "Bound every queue and every thread pool, or the failure mode becomes memory exhaustion.",
                ],
            },
            {
                "title": "Summary",
                "bullets": [
                    "Processes isolate, threads share.",
                    "Every piece of shared mutable state needs a synchronisation policy.",
                    "Pick the model by the failure you can tolerate, not by fashion.",
                ],
            },
        ],
    },
    {
        "id": "zh-06-binary-tree",
        "lang": "zh",
        "title": "二叉树与遍历",
        "subtitle": "数据结构 · 第六讲",
        "slides": [
            {
                "title": "定义",
                "bullets": [
                    "二叉树中每个结点最多有两个孩子，分别称为左孩子和右孩子。",
                    "孩子的位置有意义：只有左孩子和只有右孩子是两棵不同的树。",
                    "空树高度记为 0，只有一个结点的树高度为 1。",
                ],
            },
            {
                "title": "基本性质",
                "bullets": [
                    "高度为 h 的二叉树最多有 2^h − 1 个结点。",
                    "第 i 层最多有 2^(i−1) 个结点。",
                    "含 n 个结点的完全二叉树高度为 ⌊log2 n⌋ + 1。",
                ],
            },
            {
                "title": "满二叉树与完全二叉树",
                "bullets": [
                    "满二叉树的每一层都填满了结点。",
                    "完全二叉树除最后一层外都填满，且最后一层结点靠左连续排列。",
                    "堆就是完全二叉树，因此可以用数组连续存储。",
                ],
            },
            {
                "title": "先序遍历",
                "bullets": [
                    "访问顺序是：根、左子树、右子树。",
                    "先序序列的第一个元素一定是根。",
                    "常用于复制一棵树或输出前缀表达式。",
                ],
            },
            {
                "title": "中序遍历",
                "bullets": [
                    "访问顺序是：左子树、根、右子树。",
                    "二叉搜索树的中序遍历结果一定是从小到大有序的。",
                    "非递归实现依靠显式栈，空间为 O(h)。",
                ],
            },
            {
                "title": "后序遍历",
                "bullets": [
                    "访问顺序是：左子树、右子树、根。",
                    "后序序列的最后一个元素一定是根。",
                    "释放整棵树或计算子树大小时必须使用后序。",
                ],
            },
            {
                "title": "层序遍历",
                "bullets": [
                    "按层从左到右访问，依靠队列实现。",
                    "队列中最多同时存放一层的结点。",
                    "层序遍历可以求树的最大宽度与最小深度。",
                ],
            },
            {
                "title": "由遍历序列还原",
                "bullets": [
                    "已知中序序列与先序序列可以唯一确定一棵二叉树。",
                    "已知中序序列与后序序列也可以唯一确定。",
                    "只有先序与后序无法唯一确定，因为分不清单孩子的左右。",
                ],
            },
            {
                "title": "复杂度对比",
                "table": {
                    "header": ["遍历方式", "辅助结构", "时间", "额外空间"],
                    "rows": [
                        ["先序", "栈或递归", "O(n)", "O(h)"],
                        ["中序", "栈或递归", "O(n)", "O(h)"],
                        ["后序", "栈或递归", "O(n)", "O(h)"],
                        ["层序", "队列", "O(n)", "O(w)"],
                    ],
                },
            },
            {
                "title": "小结",
                "bullets": [
                    "三种深度优先遍历的区别只在于访问根的时机。",
                    "层序遍历需要队列，深度优先遍历需要栈或递归。",
                    "时间复杂度都是 O(n)，额外空间取决于树高或树宽。",
                ],
            },
        ],
    },
    {
        "id": "zh-07-dp",
        "lang": "zh",
        "title": "动态规划入门",
        "subtitle": "算法设计 · 第七讲",
        "slides": [
            {
                "title": "适用条件",
                "bullets": [
                    "最优子结构：原问题的最优解由子问题的最优解构成。",
                    "重叠子问题：递归求解时同一个子问题会被反复计算。",
                    "无后效性：当前状态一旦确定，后续决策与到达它的路径无关。",
                ],
            },
            {
                "title": "与分治的区别",
                "bullets": [
                    "分治把问题分成互不相交的子问题，子问题不会重复出现。",
                    "动态规划的子问题大量重叠，因此把结果存表避免重算。",
                    "记忆化搜索是自顶向下的动态规划，递推是自底向上的动态规划。",
                ],
            },
            {
                "title": "状态与转移",
                "bullets": [
                    "状态是对子问题的完整描述，必须包含做决策所需的全部信息。",
                    "状态转移方程给出大状态如何由小状态推出。",
                    "边界条件与计算顺序决定表格填得对不对。",
                ],
            },
            {
                "title": "例：斐波那契数列",
                "bullets": [
                    "递推式为 F(n) = F(n−1) + F(n−2)，边界为 F(0)=0、F(1)=1。",
                    "朴素递归的时间复杂度是 O(2^n)，因为重复计算了大量子问题。",
                    "自底向上递推只需 O(n) 时间，用滚动变量后空间为 O(1)。",
                ],
            },
            {
                "title": "例：0-1 背包",
                "bullets": [
                    "dp[i][w] 表示前 i 件物品、容量不超过 w 时的最大价值。",
                    "不选第 i 件时取 dp[i−1][w]，选时取 dp[i−1][w−wi] + vi，两者取最大。",
                    "时间复杂度 O(nW)，空间可以压成一维，但容量必须倒序枚举。",
                ],
            },
            {
                "title": "例：最长公共子序列",
                "bullets": [
                    "dp[i][j] 表示 A 的前 i 个字符与 B 的前 j 个字符的最长公共子序列长度。",
                    "字符相等时 dp[i][j] = dp[i−1][j−1] + 1，否则取上方与左方的最大值。",
                    "时间与空间复杂度都是 O(nm)。",
                ],
            },
            {
                "title": "常见错误",
                "bullets": [
                    "状态定义缺少必要信息，导致转移时用到了不存在的数据。",
                    "背包问题一维压缩时正序枚举容量，等于允许同一件物品被重复选取。",
                    "忘记处理边界，导致下标越界或初始化错误。",
                ],
            },
            {
                "title": "优化方向",
                "bullets": [
                    "滚动数组把二维空间压成一维，但必须注意枚举方向。",
                    "单调队列或四边形不等式可以把部分区间 DP 优化到 O(n^2) 甚至 O(n)。",
                    "总复杂度等于状态数乘以单次转移代价，先算这个再写代码。",
                ],
            },
            {
                "title": "解题步骤",
                "bullets": [
                    "第一步：确定状态的含义，并写出它的维度。",
                    "第二步：写出状态转移方程，检查是否覆盖所有决策。",
                    "第三步：确定边界与计算顺序，最后滚动数组优化空间。",
                ],
            },
            {
                "title": "小结",
                "bullets": [
                    "先定义状态，再写转移，最后确定边界与计算顺序。",
                    "能用记忆化搜索验证的写法，再改写成递推。",
                    "复杂度等于状态数乘以单次转移代价。",
                ],
            },
        ],
    },
    {
        "id": "zh-08-db-normalization",
        "lang": "zh",
        "title": "关系数据库：范式与索引",
        "subtitle": "数据库系统 · 第八讲",
        "slides": [
            {
                "title": "函数依赖",
                "bullets": [
                    "若 X 的取值唯一决定 Y 的取值，则称 Y 函数依赖于 X，记作 X → Y。",
                    "完全函数依赖是指 X 的任何真子集都不能决定 Y。",
                    "传递依赖是指 X → Y 且 Y → Z，而 Y 不能决定 X。",
                ],
            },
            {
                "title": "第一范式",
                "bullets": [
                    "每个属性都是不可再分的原子值。",
                    "把「地址」拆成省、市、街道，或者单独建表，都是为了满足 1NF。",
                    "数组、集合这类重复组必须拆成独立的关系。",
                ],
            },
            {
                "title": "第二范式",
                "bullets": [
                    "在 1NF 基础上，每个非主属性都完全函数依赖于候选键。",
                    "只依赖主键一部分的属性必须拆出去，否则会产生插入冗余。",
                    "联合主键的表最容易违反 2NF。",
                ],
            },
            {
                "title": "第三范式",
                "bullets": [
                    "在 2NF 基础上，非主属性不传递依赖于候选键。",
                    "把「系名 → 系主任」这类依赖单独建表即可满足 3NF。",
                    "3NF 消除了大部分更新异常。",
                ],
            },
            {
                "title": "BCNF",
                "bullets": [
                    "每个非平凡函数依赖 X → Y 的左边 X 都必须包含候选键。",
                    "BCNF 比 3NF 更严格，消除了主属性对候选键的部分依赖与传递依赖。",
                    "分解到 BCNF 可能丢失函数依赖，必要时退到 3NF 保持依赖。",
                ],
            },
            {
                "title": "B+ 树索引",
                "bullets": [
                    "B+ 树把所有键放在叶子层，并用链表连接叶子以便范围扫描。",
                    "聚簇索引的叶子存放整行数据，二级索引的叶子存放主键值再回表。",
                    "哈希索引只支持等值查询，不支持范围查询。",
                ],
            },
            {
                "title": "索引代价",
                "bullets": [
                    "索引加速读取，但每次写入都要维护索引，写多读少的表要慎重。",
                    "联合索引遵循最左前缀原则，跳过前导列无法使用索引。",
                    "区分度低的列（例如性别）建索引通常没有收益。",
                ],
            },
            {
                "title": "范式对比",
                "table": {
                    "header": ["范式", "消除的问题", "要求"],
                    "rows": [
                        ["1NF", "重复组", "属性原子化"],
                        ["2NF", "部分依赖", "非主属性完全依赖候选键"],
                        ["3NF", "传递依赖", "非主属性不传递依赖候选键"],
                        ["BCNF", "主属性的部分与传递依赖", "每个决定因素都含候选键"],
                    ],
                },
            },
            {
                "title": "执行计划",
                "bullets": [
                    "EXPLAIN 输出的 type 从 ALL 到 const 依次变好。",
                    "出现 Using filesort 或 Using temporary，说明排序或分组没有走索引。",
                    "覆盖索引让查询只读索引就能返回，避免回表。",
                ],
            },
            {
                "title": "小结",
                "bullets": [
                    "范式解决冗余与更新异常，反范式解决查询性能。",
                    "索引的本质是用写入代价换取读取代价。",
                    "先看执行计划，再决定要不要加索引。",
                ],
            },
        ],
    },
    {
        "id": "zh-09-tcp",
        "lang": "zh",
        "title": "TCP 连接管理与拥塞控制",
        "subtitle": "计算机网络 · 第九讲",
        "slides": [
            {
                "title": "三次握手",
                "bullets": [
                    "客户端发送 SYN，携带初始序号 seq = x。",
                    "服务器回复 SYN + ACK，携带自己的初始序号 seq = y 并确认 ack = x + 1。",
                    "客户端再发送 ACK = y + 1，连接建立完成。",
                ],
            },
            {
                "title": "为什么是三次",
                "bullets": [
                    "两次握手无法确认客户端的接收能力，也无法防止历史重复 SYN 建立错误连接。",
                    "三次恰好让双方都确认「我能发、你能收、你能发、我能收」。",
                    "SYN 报文不携带数据，但会消耗一个序号。",
                ],
            },
            {
                "title": "四次挥手",
                "bullets": [
                    "主动关闭方发送 FIN，进入 FIN_WAIT_1 状态。",
                    "被动关闭方先回 ACK，等自己的数据发完再发 FIN。",
                    "主动方最后进入 TIME_WAIT，等待 2MSL 后彻底关闭。",
                ],
            },
            {
                "title": "TIME_WAIT 的作用",
                "bullets": [
                    "保证最后一个 ACK 能够重传，避免被动方卡在 LAST_ACK。",
                    "让旧连接的重复报文在网络中失效，不会串到新连接。",
                    "大量 TIME_WAIT 会占用端口，可以开启 tcp_tw_reuse 缓解但需谨慎。",
                ],
            },
            {
                "title": "可靠传输",
                "bullets": [
                    "累计确认：ack 表示期望收到的下一个字节序号。",
                    "超时重传使用自适应 RTO，由 RTT 的平滑均值与偏差估算。",
                    "快速重传在收到三个重复 ACK 时立即重发，不必等待超时。",
                ],
            },
            {
                "title": "流量控制",
                "bullets": [
                    "接收方通过窗口字段通告自己还能接收多少字节。",
                    "窗口为零时发送方停止发送，并启动坚持定时器探测窗口。",
                    "窗口缩放选项把 16 位窗口扩展到最多 1 GB。",
                ],
            },
            {
                "title": "拥塞控制",
                "bullets": [
                    "慢启动阶段拥塞窗口按指数增长，每个 RTT 翻倍。",
                    "到达慢启动阈值后进入拥塞避免，每个 RTT 只增加一个 MSS。",
                    "超时把 ssthresh 减半并从 1 重新慢启动；三个重复 ACK 触发快重传与快恢复。",
                ],
            },
            {
                "title": "现代算法",
                "bullets": [
                    "CUBIC 用三次函数控制窗口增长，对高带宽长距离链路更友好。",
                    "BBR 基于带宽与最小 RTT 建模，不把丢包当作唯一的拥塞信号。",
                    "QUIC 在用户态实现拥塞控制，并把握手与加密合并以减少 RTT。",
                ],
            },
            {
                "title": "状态与阶段",
                "table": {
                    "header": ["阶段", "触发", "窗口变化"],
                    "rows": [
                        ["慢启动", "连接开始或超时", "每个 RTT 翻倍"],
                        ["拥塞避免", "cwnd ≥ ssthresh", "每个 RTT 加 1 MSS"],
                        ["快重传", "三个重复 ACK", "立即重发丢失报文"],
                        ["快恢复", "快重传之后", "ssthresh 减半后继续增长"],
                    ],
                },
            },
            {
                "title": "小结",
                "bullets": [
                    "三次握手解决序号同步与双向可达确认。",
                    "四次挥手解决半关闭，TIME_WAIT 保护最后一个 ACK。",
                    "拥塞控制决定发送速率，流量控制决定接收能力。",
                ],
            },
        ],
    },
    {
        "id": "zh-10-backprop",
        "lang": "zh",
        "title": "神经网络与反向传播",
        "subtitle": "机器学习 · 第十讲",
        "slides": [
            {
                "title": "前向传播",
                "bullets": [
                    "第 l 层的输出为 a^l = f(W^l a^(l−1) + b^l)。",
                    "f 是激活函数，常见的有 ReLU、Sigmoid 与 Tanh。",
                    "最后一层的输出经过损失函数得到一个标量误差。",
                ],
            },
            {
                "title": "损失函数",
                "bullets": [
                    "回归任务常用均方误差 MSE，分类任务常用交叉熵。",
                    "交叉熵与 softmax 组合后梯度形式简洁：∂L/∂z = ŷ − y。",
                    "损失函数必须可微，否则无法反向传播。",
                ],
            },
            {
                "title": "梯度下降",
                "bullets": [
                    "参数更新规则为 θ ← θ − η ∂L/∂θ。",
                    "学习率过大会震荡发散，过小则收敛缓慢。",
                    "Adam 用梯度的一阶矩与二阶矩估计自适应调整每个参数的学习率。",
                ],
            },
            {
                "title": "链式法则",
                "bullets": [
                    "复合函数的导数等于各层局部导数的乘积。",
                    "反向传播从输出层向输入层逐层计算误差对每个参数的偏导。",
                    "一次前向加一次反向的代价约为纯前向的三倍。",
                ],
            },
            {
                "title": "反向传播公式",
                "bullets": [
                    "输出层误差为 δ^L = ∇_a L ⊙ f'(z^L)。",
                    "隐藏层误差为 δ^l = (W^(l+1))^T δ^(l+1) ⊙ f'(z^l)。",
                    "参数梯度为 ∂L/∂W^l = δ^l (a^(l−1))^T，∂L/∂b^l = δ^l。",
                ],
            },
            {
                "title": "激活函数与梯度",
                "bullets": [
                    "Sigmoid 的导数最大只有 0.25，深层网络容易梯度消失。",
                    "ReLU 在正区间导数为 1，缓解梯度消失但可能出现死亡神经元。",
                    "批归一化让每层输入分布稳定，允许使用更大的学习率。",
                ],
            },
            {
                "title": "常见问题",
                "bullets": [
                    "梯度爆炸可以用梯度裁剪或更好的权重初始化缓解。",
                    "过拟合用正则化、Dropout 与早停来控制。",
                    "训练损失下降而验证损失上升，就是过拟合的典型信号。",
                ],
            },
            {
                "title": "实践检查清单",
                "bullets": [
                    "先用小批量数据过拟合一次，确认模型与损失实现正确。",
                    "检查输入是否归一化、标签是否对齐、学习率是否合理。",
                    "记录训练与验证曲线，而不是只看最后一个数字。",
                ],
            },
            {
                "title": "训练循环",
                "bullets": [
                    "第一步：前向计算输出并求损失。",
                    "第二步：反向传播求梯度。",
                    "第三步：更新参数并清零梯度，进入下一批数据。",
                ],
            },
            {
                "title": "小结",
                "bullets": [
                    "前向传播计算输出，反向传播计算梯度。",
                    "链式法则是整个训练流程的数学基础。",
                    "梯度消失、梯度爆炸与过拟合是工程上最常见的三类问题。",
                ],
            },
        ],
    },
]

#: Decks that also get a PDF rendering, so the pdfplumber path is exercised for both scripts.
PDF_DECK_IDS = ("en-01-sorting", "en-04-shortest-paths", "zh-06-binary-tree", "zh-09-tcp")
