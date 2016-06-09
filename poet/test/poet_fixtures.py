# flake8:noqa

old_style_pypi_json = r"""
{
    "info": {
        "maintainer": null,
        "docs_url": null,
        "requires_python": null,
        "maintainer_email": null,
        "cheesecake_code_kwalitee_id": null,
        "keywords": null,
        "package_url": "http://pypi.python.org/pypi/eleven",
        "author": "Tim D. Smith",
        "author_email": "eleven@tim-smith.us",
        "download_url": "UNKNOWN",
        "platform": "any",
        "version": "0.1.1",
        "cheesecake_documentation_id": null,
        "_pypi_hidden": false,
        "description": "eleven\n======\n\nTim D. Smith, [@biotimylated](https://twitter.com/biotimylated)\n\nEleven is a Python library for performing multi-gene RT-qPCR gene\nexpression normalization. It is a free, open-source implementation of\nthe `GeNorm\nalgorithm <http://dx.doi.org/10.1186/gb-2002-3-7-research0034>`__\ndescribed by Vandesompele et al. in 2002.\n\n`Documentation <http://eleven.readthedocs.org>`__ is hosted at Read the\nDocs.\n\nHow do I use eleven?\n--------------------\n\nEleven requires Python 2.7. Earlier versions will not be supported.\nPython 3.x support is on the roadmap. You will need a Scientific Python\nstack, including pandas and scipy. If you don't have these, you can\ninstall the free version of the `Anaconda\nenvironment <https://store.continuum.io/cshop/anaconda/>`__, which has\neverything you need.\n\nA sample analysis session looks like this:\n\n::\n\n    # Read PCR data into a pandas DataFrame. You want a data file where each\n    # row corresponds to a separate well, with columns for the sample name,\n    # target name, and Cq value. NTC wells should have the sample name set to\n    # a value like 'NTC'.\n    >> df = pd.read_csv('my_data.csv')\n\n    # If your Sample, Target, and Cq columns are called other things, they\n    # should be renamed to Sample, Target, and Cq.\n    >> df = df.rename(columns={'Gene': 'Target', 'Ct': 'Cq'})\n\n    # Drop the wells that are too close to the NTC for that target.\n    >> censored = eleven.censor_background(df)\n\n    # Rank your candidate reference genes.\n    >> ranked = eleven.rank_targets(censored, ['Gapdh', 'Rn18s', 'Hprt',\n        'Ubc', 'Actb'], 'Control')\n\n    # Normalize your data by your most stable genes and compute normalization\n    # factors (NFs).\n    >> nf = eleven.calculate_nf(censored, ranked.ix['Target', 0:3], 'Control')\n\n    # Now, normalize all of your expression data.\n    >> censored['RelExp'] = eleven.expression_nf(censored, nf, 'Control')\n\nWasn't that easy? This adds the relative expression of each well as a\ncolumn of the data frame. Now you can use regular pandas tools for\nhandling the data, so\n``censored.groupby(['Sample', 'Target'])['RelExp'].aggregate(['mean', 'std'])``\ngives you a nice table of means and standard deviations for each target\nin each sample.\n\nIsn't Gapdh/Actb/Rn18s good enough?\n-----------------------------------\n\nIf you're expecting 40-fold changes in your experiments, normalizing\nagainst a single \"usual suspect\" reference gene will probably do it.\n\nBut if you're interested in reliably measuring smaller changes, remember\nthat the quality of your results cannot be better than the quality of\nyour normalization. Without at least assessing the stability of your\nfavorite reference gene under your experimental conditions against a\npanel of other genes that are likely to be more or less stably\nexpressed, the systematic error of your comparison is totally\nuncontrolled. **Unless you show your reference gene is quantitatively\nstable, you have no evidence you are running a quantitative\nexperiment.**\n\nWhy GeNorm?\n-----------\n\nSeveral algorithms have been proposed and are in use for selecting an\nensemble of stably expressed targets from a panel of candidate reference\ngenes. GeNorm is one of the older and more popular algorithms. A `2009\nreview by Vandesompele, Kubista, and\nPfaffl <http://www.gene-quantification.de/Vandesompele-Kubista-Pfaffl-real-time-PCR-chapter-4.pdf>`__\nexplains the mathematical basis behind several normalization algorithms\nand concludes while \"every scientist should at least validate their\nreference genes, the actual method used [to normalize genes] is less\ncritical\" since they give \"highly similar rankings.\"\n\nAdding other algorithms isn't a priority for me but I'll gladly accept\npull requests supported by regression tests.\n\nWhy should I use eleven?\n------------------------\n\nEleven has a simple, clean interface and uses familiar data structures.\nAlso, I think we're the only game in town for PCR analysis in Python.\n\nThere are other options in R;\n`SLqPCR <http://www.bioconductor.org/packages/devel/bioc/html/SLqPCR.html>`__\nis probably the most kindred to eleven.\n`qpcR <http://www.dr-spiess.de/qpcR.html>`__ does a number of very\nsophisticated things but I found it correspondingly mysterious. `But I\ndon't like R <http://tim-smith.us/arrgh/>`__.\n\nWhy is it named eleven?\n-----------------------\n\nPCR is amplification based. `Our amplifier goes to\n11. <https://en.wikipedia.org/wiki/Up_to_eleven>`__",
        "release_url": "http://pypi.python.org/pypi/eleven/0.1.1",
        "downloads": {
            "last_month": 1,
            "last_week": 0,
            "last_day": 0
        },
        "_pypi_ordering": 1,
        "classifiers": [
            "Development Status :: 4 - Beta",
            "Intended Audience :: Science/Research",
            "License :: OSI Approved :: BSD License",
            "Natural Language :: English",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Programming Language :: Python :: 2.7",
            "Topic :: Scientific/Engineering :: Bio-Informatics",
            "Topic :: Software Development :: Libraries :: Python Modules"
        ],
        "bugtrack_url": null,
        "name": "eleven",
        "license": "BSD",
        "summary": "A friendly implementation of the GeNorm multi-gene RT-qPCR normalization algorithm",
        "home_page": "http://github.com/tdsmith/eleven/",
        "cheesecake_installability_id": null
    },
    "releases": {
        "0.1": [
            {
                "has_sig": false,
                "upload_time": "2014-02-20T20:39:44",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/0e/e2/60c37900e25396ac91476f5f1ebfc615ea2f6f85d6201eb9193a8902fe45/eleven-0.1.tar.gz",
                "md5_digest": "d2895f359809b1a5918f0f9765d300d1",
                "downloads": 1853,
                "filename": "eleven-0.1.tar.gz",
                "packagetype": "sdist",
                "path": "0e/e2/60c37900e25396ac91476f5f1ebfc615ea2f6f85d6201eb9193a8902fe45/eleven-0.1.tar.gz",
                "size": 172232
            }
        ],
        "0.1.1": [
            {
                "has_sig": false,
                "upload_time": "2014-02-21T06:58:27",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/bc/d6/a3c610736463dd70823f8a2736061870605dcd115f36803048d272396eb2/eleven-0.1.1.tar.gz",
                "md5_digest": "a7d6a569c484b20f5b0c5cc6a92ec8eb",
                "downloads": 2255,
                "filename": "eleven-0.1.1.tar.gz",
                "packagetype": "sdist",
                "path": "bc/d6/a3c610736463dd70823f8a2736061870605dcd115f36803048d272396eb2/eleven-0.1.1.tar.gz",
                "size": 172402
            }
        ]
    },
    "urls": [
        {
            "has_sig": false,
            "upload_time": "2014-02-21T06:58:27",
            "comment_text": "",
            "python_version": "source",
            "url": "https://pypi.python.org/packages/bc/d6/a3c610736463dd70823f8a2736061870605dcd115f36803048d272396eb2/eleven-0.1.1.tar.gz",
            "md5_digest": "a7d6a569c484b20f5b0c5cc6a92ec8eb",
            "downloads": 2255,
            "filename": "eleven-0.1.1.tar.gz",
            "packagetype": "sdist",
            "path": "bc/d6/a3c610736463dd70823f8a2736061870605dcd115f36803048d272396eb2/eleven-0.1.1.tar.gz",
            "size": 172402
        }
    ]
}
"""
