"""
Examines successful raw tool results produced during the current iteration and
creates prompt-friendly evidence records grounded in those results.

The evidence records remain iteration-local until the next iteration's context
evaluation accepts and incorporates them into the working context.
"""