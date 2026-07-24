"""
Applies the context evaluation produced at the beginning of the iteration.

Updates the cumulative working context, incorporates accepted evidence from the
immediately preceding iteration, updates plan progress, stores the evaluation
as the working context's latest evaluation, and adds the same evaluation to the
current iteration record builder.
"""