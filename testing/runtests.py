#!/usr/bin/python

from __future__ import print_function
import argparse, glob, itertools, re, shutil, os, sys

config_reg = re.compile('.*\/\/\s*(?P<name>\S+):\s*(?P<value>.*)$')

class Tester:
	def __init__(self,args,test):
		self.args      = args
		self.test      = test
		self.update    = args.updateref
		self.config    = self.get_config()
		self.test_name = '[%s]: %s' % (self.test,self.config['objective'][0])
		self.test_id   = self.test.split('_')[0]
		if self.update:
			self.test_out = self.args.inputdir+'/'+self.test_id
		else:
			self.test_out = self.args.outputdir+'/test_output_'+self.test_id
		self.prepare_test()

	def compare_ok(self,got_file,expected_file,name):
		if not os.path.isfile(got_file):
			return (True,'%s absent' % got_file)
		elif not os.path.isfile(expected_file):
			return (True,'%s absent' % expected_file)
		else:
			diff = os.popen('diff -b -w -u %s %s' % (got_file,expected_file)).read()
			if diff and not diff.startswith("No differences"):
				return (True,'Difference between generated output and reference:\n%s' % diff)
		return (False,'')

	def cleanup_xmllint(self,errmsg):
		msg = errmsg.split('\n')
		rtnmsg = ""
		for o in msg:
			if (o):
				if (o.startswith("I/O error : Attempt")):
					pass
				else:
					if (rtnmsg):
						rtnmsg += '\n'
					rtnmsg += o
		return rtnmsg

	def get_config(self):
		config = {}
		with open(self.args.inputdir+'/'+self.test,'r') as f:
			for line in f.readlines():
				m = config_reg.match(line)
				if m:
					key   = m.group('name')
					value = m.group('value')
					if (key=='config'):
						value = value.replace('$INPUTDIR',self.args.inputdir)
					#print('key=%s value=%s' % (key,value))
					config.setdefault(key, []).append(value)
		return config

	def prepare_test(self):
		# prepare test environment
		shutil.rmtree(self.test_out,ignore_errors=True)
		os.mkdir(self.test_out)
		shutil.copy(self.args.inputdir+'/Doxyfile',self.test_out)
		with open(self.test_out+'/Doxyfile','a') as f:
			print('INPUT=%s/%s' % (self.args.inputdir,self.test), file=f)
			print('STRIP_FROM_PATH=%s' % self.args.inputdir, file=f)
			print('EXAMPLE_PATH=%s' % self.args.inputdir, file=f)
			if 'config' in self.config:
				for option in self.config['config']:
					print(option, file=f)
			if (self.args.xml):
				print('GENERATE_XML=YES', file=f)
				print('XML_OUTPUT=%s/out' % self.test_out, file=f)
			else:
				print('GENERATE_XML=NO', file=f)
			if (self.args.xhtml):
				print('GENERATE_HTML=YES', file=f)
			# HTML_OUTPUT can also be set locally
			print('HTML_OUTPUT=%s/html' % self.test_out, file=f)
			print('HTML_FILE_EXTENSION=.xhtml', file=f)
			if (self.args.pdf):
				print('GENERATE_LATEX=YES', file=f)
				print('LATEX_OUTPUT=%s/latex' % self.test_out, file=f)

		if 'check' not in self.config or not self.config['check']:
			print('Test doesn\'t specify any files to check')
			sys.exit(1)

		# run doxygen
		if (sys.platform == 'win32'):
			redir=' > nul:'
		else:
			redir=' 2> /dev/null > /dev/null'

		if (self.args.noredir):
			redir=''

		if os.system('%s %s/Doxyfile %s' % (self.args.doxygen,self.test_out,redir))!=0:
			print('Error: failed to run %s on %s/Doxyfile' % (self.args.doxygen,self.test_out));
			sys.exit(1)

	# update the reference data for this test
	def update_test(self,testmgr):
		print('Updating reference for %s' % self.test_name)

		if 'check' in self.config:
			for check in self.config['check']:
				check_file='%s/out/%s' % (self.test_out,check)
				# check if the file we need to check is actually generated
				if not os.path.isfile(check_file):
					print('Non-existing file %s after \'check:\' statement' % check_file)
					return
				# convert output to canonical form
				data = os.popen('%s --format --noblanks --nowarning %s' % (self.args.xmllint,check_file)).read()
				if data:
					# strip version
					data = re.sub(r'xsd" version="[0-9.-]+"','xsd" version=""',data).rstrip('\n')
				else:
					print('Failed to run %s on the doxygen output file %s' % (self.args.xmllint,self.test_out))
					return
				out_file='%s/%s' % (self.test_out,check)
				with open(out_file,'w') as f:
					print(data,file=f)
		shutil.rmtree(self.test_out+'/out',ignore_errors=True)
		os.remove(self.test_out+'/Doxyfile')

	# check the relevant files of a doxygen run with the reference material
	def perform_test(self,testmgr):
		if (sys.platform == 'win32'):
			redir=' > nul:'
			separ='&'
		else:
			redir=' 2> /dev/null'
			separ=';'

		if (self.args.noredir):
			redir=''

		failed_xml=False
		failed_html=False
		failed_latex=False
		msg = ()
		# look for files to check against the reference
		if self.args.xml:
			failed_xml=True
			if 'check' in self.config:
				for check in self.config['check']:
					check_file='%s/out/%s' % (self.test_out,check)
					# check if the file we need to check is actually generated
					if not os.path.isfile(check_file):
						msg += ('Non-existing file %s after \'check:\' statement' % check_file,)
						break
					# convert output to canonical form
					data = os.popen('%s --format --noblanks --nowarning %s' % (self.args.xmllint,check_file)).read()
					if data:
						# strip version
						data = re.sub(r'xsd" version="[0-9.-]+"','xsd" version=""',data).rstrip('\n')
					else:
						msg += ('Failed to run %s on the doxygen output file %s' % (self.args.xmllint,self.test_out),)
						break
					out_file='%s/%s' % (self.test_out,check)
					with open(out_file,'w') as f:
						print(data,file=f)
					ref_file='%s/%s/%s' % (self.args.inputdir,self.test_id,check)
					(failed_xml,xml_msg) = self.compare_ok(out_file,ref_file,self.test_name)
					if failed_xml:
						msg+= (xml_msg,)
						break
				if not failed_xml and not self.args.keep:
					xml_output='%s/out' % self.test_out
					shutil.rmtree(xml_output,ignore_errors=True)

		if (self.args.xhtml):
			html_output='%s/html' % self.test_out
			if (sys.platform == 'win32'):
				redirx=' 2> %s/temp >nul:'%html_output
			else:
				redirx='2>%s/temp >/dev/null'%html_output
			exe_string = '%s --path dtd --nonet --postvalid %s/*xhtml %s %s ' % (self.args.xmllint,html_output,redirx,separ)
			exe_string += 'more "%s/temp"' % (html_output)
			failed_html=False
			xmllint_out = os.popen(exe_string).read()
			xmllint_out = self.cleanup_xmllint(xmllint_out)
			if xmllint_out:
				msg += (xmllint_out,)
				failed_html=True
			elif not self.args.keep:
				shutil.rmtree(html_output,ignore_errors=True)
		if (self.args.pdf):
			failed_latex=False
			latex_output='%s/latex' % self.test_out
			if (sys.platform == 'win32'):
				redirl='>nul: 2>temp'
			else:
				redirl='>/dev/null 2>temp'
			exe_string = 'cd %s %s echo "q" | make %s %s' % (latex_output,separ,redirl,separ)
			exe_string += 'more temp'
			latex_out = os.popen(exe_string).read()
			if latex_out.find("Error")!=-1:
				msg += ("PDF generation failed\n  For a description of the problem see 'refman.log' in the latex directory of this test",)
				failed_html=True
			elif open(latex_output + "/refman.log",'r').read().find("Emergency stop")!= -1:
				msg += ("PDF generation failed\n  For a description of the problem see 'refman.log' in the latex directory of this test",)
				failed_html=True
			elif not self.args.keep:
				shutil.rmtree(latex_output,ignore_errors=True)

		if failed_xml or failed_html or failed_latex:
			testmgr.ok(False,self.test_name,msg)
			return

		testmgr.ok(True,self.test_name)
		if not self.args.keep:
			shutil.rmtree(self.test_out,ignore_errors=True)

	def run(self,testmgr):
		if self.update:
			self.update_test(testmgr)
		else:
			self.perform_test(testmgr)

class TestManager:
	def __init__(self,args,tests):
		self.args  = args
		self.tests = tests
		self.num_tests = len(tests)
		self.count=1
		self.passed=0
		if self.args.xhtml:
			self.prepare_dtd()
		print('1..%d' % self.num_tests)

	def ok(self,result,test_name,msg='Ok'):
		if result:
			print('ok %s - %s' % (self.count,test_name))
			self.passed = self.passed + 1
		else:
			print('not ok %s - %s' % (self.count,test_name))
			print('-------------------------------------')
			for o in msg:
				print(o)
				print('-------------------------------------')
		self.count = self.count + 1

	def result(self):
		if self.passed==self.num_tests:
			print('All tests passed!')
		else:
			print('%d out of %s tests failed' % (self.num_tests-self.passed,self.num_tests))
		return 0 if self.passed==self.num_tests else 1

	def perform_tests(self):
		for test in self.tests:
			tester = Tester(self.args,test)
			tester.run(self)
		res=self.result()
		if self.args.xhtml and not res and not self.args.keep:
			shutil.rmtree("dtd",ignore_errors=True)
		return 0 if self.args.updateref else res

	def prepare_dtd(self):
		shutil.rmtree("dtd",ignore_errors=True)
		shutil.copytree(self.args.inputdir+"/dtd", "dtd")

def main():
	# argument handling
	parser = argparse.ArgumentParser(description='run doxygen tests')
	parser.add_argument('--updateref',help=
		'update the reference files. Should be used in combination with -id to '
                'update the reference file(s) for the given test',action="store_true")
	parser.add_argument('--doxygen',nargs='?',default='doxygen',help=
		'path/name of the doxygen executable')
	parser.add_argument('--xmllint',nargs='?',default='xmllint',help=
		'path/name of the xmllint executable')
	parser.add_argument('--id',nargs='+',dest='ids',action='append',type=int,help=
		'run test with number n only (the option may be specified run test with '
		'number n only (the option may be specified')
	parser.add_argument('--all',help=
		'can be used in combination with -updateref to update the reference files '
		'for all tests.',action="store_true")
	parser.add_argument('--inputdir',nargs='?',default='.',help=
		'input directory containing the tests')
	parser.add_argument('--outputdir',nargs='?',default='.',help=
		'output directory to write the doxygen output to')
	parser.add_argument('--noredir',help=
		'disable redirection of doxygen warnings',action="store_true")
	parser.add_argument('--xml',help='create xml output and check',
		action="store_true")
	parser.add_argument('--xhtml',help=
		'create xhtml output and check with xmllint',action="store_true")
	parser.add_argument('--pdf',help='create LaTeX output and create pdf from it',
		action="store_true")
	parser.add_argument('--keep',help='keep result directories',
		action="store_true")
	args = parser.parse_args()

	# sanity check
	if (not args.xml) and (not args.pdf) and (not args.xhtml):
		args.xml=True
	if (not args.updateref is None) and (args.ids is None) and (args.all is None):
		parser.error('--updateref requires either --id or --all')

	starting_directory = os.getcwd()
	os.chdir(args.inputdir)
	# find the tests to run
	if args.ids: # test ids are given by user
		tests = []
		for id in list(itertools.chain.from_iterable(args.ids)):
			tests.append(glob.glob('%s_*'%id))
			tests.append(glob.glob('0%s_*'%id))
			tests.append(glob.glob('00%s_*'%id))
		tests = list(itertools.chain.from_iterable(tests))
	else: # find all tests
		tests = glob.glob('[0-9][0-9][0-9]_*')
	os.chdir(starting_directory)

	# create test manager to run the tests
	testManager = TestManager(args,tests)
	sys.exit(testManager.perform_tests())

if __name__ == '__main__':
	main()
